"""
Stripe Checkout Session integration for ecommerce checkouts.

Uses Checkout Sessions (hosted payment page). Order fulfillment runs after
``checkout.session.completed`` webhook (or immediately for zero-total carts).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction

import stripe

from ecommerce.constants.checkout import CHECKOUT_STATUS_OPEN, ORDER_FINANCIAL_PAID
from ecommerce.models.checkout import Checkout, Order
from ecommerce.services import checkout_pricing
from ecommerce.services.checkout_payment_settings import (
    stripe_checkout_available,
    stripe_unavailable_reason,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeCheckoutError(Exception):
    """Raised when Stripe is misconfigured or the API returns an error."""


def stripe_enabled() -> bool:
    """True when Stripe Checkout is enabled in admin and configured in the environment."""
    return stripe_checkout_available()


def _amount_cents(amount: Decimal) -> int:
    return int(checkout_pricing.quantize_money(amount) * 100)


def checkout_amount_due(checkout: Checkout) -> Decimal:
    checkout_pricing.recalculate_checkout(checkout)
    checkout.refresh_from_db()
    return Decimal(checkout_pricing.checkout_totals(checkout)["total"])


def _currency_code(checkout: Checkout) -> str:
    return (checkout.currency or "USD").lower()


def _build_line_items(checkout: Checkout) -> list[dict]:
    """Stripe line items; amounts must sum to at least the session total."""
    items: list[dict] = []
    currency = _currency_code(checkout)

    for li in checkout.line_items.select_related("variant__product"):
        product = li.variant.product
        items.append(
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": _amount_cents(li.unit_price),
                    "product_data": {
                        "name": f"{product.title} — {li.variant.title}",
                        "metadata": {
                            "variant_id": str(li.variant_id),
                            "product_id": str(product.pk),
                        },
                    },
                },
                "quantity": li.quantity,
            }
        )

    if checkout.shipping_total > Decimal("0.00"):
        items.append(
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": _amount_cents(checkout.shipping_total),
                    "product_data": {"name": "Shipping"},
                },
                "quantity": 1,
            }
        )

    if checkout.tax_total > Decimal("0.00"):
        items.append(
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": _amount_cents(checkout.tax_total),
                    "product_data": {"name": "Tax"},
                },
                "quantity": 1,
            }
        )

    return items


def _session_discounts(checkout: Checkout, line_items: list[dict]) -> list[dict] | None:
    """
    Gift cards and cart discounts reduce the amount due below line-item sum;
    apply a one-time Stripe coupon for the difference.
    """
    due = checkout_amount_due(checkout)
    if due <= Decimal("0.00"):
        return None

    gross = Decimal("0.00")
    for item in line_items:
        gross += Decimal(item["price_data"]["unit_amount"]) * item["quantity"] / 100

    reduction = checkout_pricing.quantize_money(gross - due)
    if reduction <= Decimal("0.00"):
        return None

    coupon = stripe.Coupon.create(
        amount_off=_amount_cents(reduction),
        currency=_currency_code(checkout),
        duration="once",
        name=f"Checkout {checkout.pk} adjustments",
        metadata={"checkout_id": str(checkout.pk)},
    )
    return [{"coupon": coupon.id}]


def create_checkout_payment_session(
    checkout: Checkout,
    *,
    success_url: str,
    cancel_url: str,
    customer_user_id: int | None = None,
) -> dict:
    """
    Create or refresh a Stripe Checkout Session for an open checkout.

    Returns dict with checkout_url, session_id, publishable_key.
    """
    if not stripe_enabled():
        reason = stripe_unavailable_reason() or "Stripe Checkout is not available."
        raise StripeCheckoutError(reason)

    if checkout.status != CHECKOUT_STATUS_OPEN:
        raise StripeCheckoutError("Checkout is not open.")

    if not checkout.line_items.exists():
        raise StripeCheckoutError("Checkout has no line items.")

    checkout_pricing.recalculate_checkout(checkout)
    checkout.refresh_from_db()

    due = checkout_amount_due(checkout)
    if due <= Decimal("0.00"):
        raise StripeCheckoutError(
            "Nothing to charge. Use POST /checkouts/{id}/complete/ for zero-total orders."
        )

    if not checkout.email:
        raise StripeCheckoutError("Checkout email is required before payment.")

    line_items = _build_line_items(checkout)
    if not line_items:
        raise StripeCheckoutError("Could not build payment line items.")

    metadata = {"checkout_id": str(checkout.pk)}
    if customer_user_id:
        metadata["customer_user_id"] = str(customer_user_id)

    session_kwargs: dict = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_email": checkout.email,
        "client_reference_id": str(checkout.token),
        "line_items": line_items,
        "metadata": metadata,
    }

    discounts = _session_discounts(checkout, line_items)
    if discounts:
        session_kwargs["discounts"] = discounts

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.StripeError as exc:
        raise StripeCheckoutError(str(exc)) from exc

    checkout.stripe_checkout_session_id = session.id
    checkout.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


@transaction.atomic
def fulfill_checkout_from_stripe_session(
    session_id: str,
    *,
    payment_intent_id: str | None = None,
    require_paid: bool = True,
) -> Order | None:
    """
    Complete checkout after Stripe payment. Idempotent if already completed.

    Returns the Order, or None if the session is not ready / not found.
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError:
        return None

    if require_paid and session.payment_status != "paid":
        return None

    if payment_intent_id is None:
        payment_intent_id = session.payment_intent or ""

    meta = session.metadata or {}
    customer = None
    meta_user = meta.get("customer_user_id")
    if meta_user and str(meta_user).isdigit():
        from django.contrib.auth import get_user_model

        customer = get_user_model().objects.filter(pk=int(meta_user)).first()

    checkout = (
        Checkout.objects.select_for_update()
        .filter(stripe_checkout_session_id=session_id)
        .first()
    )
    if checkout is None:
        raw_id = meta.get("checkout_id")
        if raw_id and str(raw_id).isdigit():
            checkout = (
                Checkout.objects.select_for_update()
                .filter(pk=int(raw_id))
                .first()
            )
            if checkout and not checkout.stripe_checkout_session_id:
                checkout.stripe_checkout_session_id = session_id
                checkout.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    if checkout is None:
        return None

    if checkout.status != CHECKOUT_STATUS_OPEN:
        return Order.objects.filter(checkout=checkout).first()

    return checkout_pricing.complete_checkout(
        checkout,
        customer=customer,
        financial_status=ORDER_FINANCIAL_PAID,
        stripe_payment_intent_id=payment_intent_id or "",
    )


def handle_stripe_webhook_event(payload: bytes, sig_header: str) -> str:
    """
    Verify and process a Stripe webhook. Returns a short status string for logging.
    """
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise StripeCheckoutError("STRIPE_WEBHOOK_SECRET is not configured.")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError as exc:
        raise StripeCheckoutError("Invalid webhook payload.") from exc
    except stripe.SignatureVerificationError as exc:
        raise StripeCheckoutError("Invalid webhook signature.") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        if session_id:
            fulfill_checkout_from_stripe_session(
                session_id,
                payment_intent_id=session.get("payment_intent") or "",
            )
        return "checkout.session.completed"

    if event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        Checkout.objects.filter(
            stripe_checkout_session_id=session.get("id"),
            status=CHECKOUT_STATUS_OPEN,
        ).update(stripe_checkout_session_id="")
        return "checkout.session.expired"

    return f"ignored:{event['type']}"
