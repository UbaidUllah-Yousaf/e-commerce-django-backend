"""Load store-wide checkout payment options (singleton row)."""

from __future__ import annotations

from django.conf import settings

from ecommerce.constants.storefront import (
    STOREFRONT_CHECKOUT_CANCEL_PATH,
    STOREFRONT_CHECKOUT_SUCCESS_PATH,
    STRIPE_SESSION_QUERY_PARAM,
)
from ecommerce.models.checkout_payment import CheckoutPaymentSettings


def build_checkout_redirect_urls(
    base_url: str | None = None,
    *,
    success_path: str | None = None,
    cancel_path: str | None = None,
) -> dict[str, str]:
    """
    Build Stripe success/cancel URLs for a React + Vite storefront.

    ``success_url`` includes ``{CHECKOUT_SESSION_ID}`` for Stripe Checkout.
    The success page should read ``session_id`` from the query string after redirect.
    """
    base = (
        base_url
        or getattr(settings, "STOREFRONT_BASE_URL", "")
        or "http://localhost:5173"
    ).rstrip("/")
    success = success_path or getattr(
        settings,
        "STOREFRONT_CHECKOUT_SUCCESS_PATH",
        STOREFRONT_CHECKOUT_SUCCESS_PATH,
    )
    cancel = cancel_path or getattr(
        settings,
        "STOREFRONT_CHECKOUT_CANCEL_PATH",
        STOREFRONT_CHECKOUT_CANCEL_PATH,
    )
    if not success.startswith("/"):
        success = f"/{success}"
    if not cancel.startswith("/"):
        cancel = f"/{cancel}"

    return {
        "success_url": (
            f"{base}{success}?{STRIPE_SESSION_QUERY_PARAM}={{CHECKOUT_SESSION_ID}}"
        ),
        "cancel_url": f"{base}{cancel}",
    }


def _initial_defaults() -> dict:
    urls = build_checkout_redirect_urls()
    return {
        "stripe_checkout_enabled": True,
        "allow_cod_complete": False,
        "default_success_url": urls["success_url"],
        "default_cancel_url": urls["cancel_url"],
        "checkout_payment_note": "",
    }


def get_checkout_payment_settings() -> CheckoutPaymentSettings:
    obj, _ = CheckoutPaymentSettings.objects.get_or_create(pk=1, defaults=_initial_defaults())
    return obj


def get_effective_checkout_redirect_urls() -> dict[str, str]:
    """Admin overrides, else URLs generated from STOREFRONT_BASE_URL (Vite dev default)."""
    opts = get_checkout_payment_settings()
    generated = build_checkout_redirect_urls()
    return {
        "success_url": (opts.default_success_url or "").strip() or generated["success_url"],
        "cancel_url": (opts.default_cancel_url or "").strip() or generated["cancel_url"],
        "generated_success_url": generated["success_url"],
        "generated_cancel_url": generated["cancel_url"],
    }


def stripe_keys_configured() -> bool:
    """Stripe API keys are present in environment / Django settings."""
    secret = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    publishable = (getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "").strip()
    return bool(secret and publishable)


def stripe_checkout_available() -> bool:
    """Stripe Checkout is enabled in admin and API keys are configured."""
    if not stripe_keys_configured():
        return False
    return get_checkout_payment_settings().stripe_checkout_enabled


def stripe_unavailable_reason() -> str:
    """Human-readable reason Stripe is not operational (empty when available)."""
    opts = get_checkout_payment_settings()
    if not opts.stripe_checkout_enabled:
        return "Stripe Checkout is disabled in Checkout payment settings."
    if not stripe_keys_configured():
        missing = []
        if not (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip():
            missing.append("STRIPE_SECRET_KEY")
        if not (getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "").strip():
            missing.append("STRIPE_PUBLISHABLE_KEY")
        return (
            f"Add {', '.join(missing)} to ecommerce/.env (see .env.example), then restart the server."
        )
    return ""


def get_stripe_status() -> dict:
    """Stripe readiness for API responses and admin display."""
    opts = get_checkout_payment_settings()
    keys = stripe_keys_configured()
    admin_on = opts.stripe_checkout_enabled
    available = admin_on and keys
    return {
        "stripe_checkout_enabled": admin_on,
        "stripe_keys_configured": keys,
        "stripe_checkout_available": available,
        "unavailable_reason": stripe_unavailable_reason() if not available else "",
    }


def cod_complete_allowed() -> bool:
    return get_checkout_payment_settings().allow_cod_complete


def payment_required_for_checkout(total) -> bool:
    """Whether the storefront must use Stripe (COD and zero-total bypass)."""
    from decimal import Decimal

    from ecommerce.services import checkout_pricing

    amount = checkout_pricing.quantize_money(Decimal(str(total)))
    if amount <= Decimal("0.00"):
        return False
    if not stripe_checkout_available():
        return False
    if cod_complete_allowed():
        return False
    return True


def resolve_checkout_redirect_urls(
    success_url: str | None,
    cancel_url: str | None,
) -> tuple[str, str]:
    """Use request body, admin defaults, or generated Vite URLs."""
    effective = get_effective_checkout_redirect_urls()
    success = (success_url or "").strip() or effective["success_url"]
    cancel = (cancel_url or "").strip() or effective["cancel_url"]
    if "{CHECKOUT_SESSION_ID}" not in success:
        raise ValueError("success_url must include {CHECKOUT_SESSION_ID}.")
    return success, cancel
