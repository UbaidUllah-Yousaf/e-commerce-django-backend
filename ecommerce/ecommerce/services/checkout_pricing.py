from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from ecommerce.constants.checkout import (
    CHECKOUT_STATUS_COMPLETED,
    CHECKOUT_STATUS_OPEN,
    ORDER_FINANCIAL_PAID,
)
from ecommerce.constants.discount import DISCOUNT_TYPE_PERCENTAGE
from ecommerce.models.checkout import (
    Checkout,
    CheckoutGiftCardApplication,
    Order,
    OrderLineItem,
)
from ecommerce.models.discount import DiscountCode
from ecommerce.models.gift_card import GiftCard
from ecommerce.models.product import ProductVariant


MONEY = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def line_items_subtotal(checkout: Checkout) -> Decimal:
    total = Decimal("0.00")
    for li in checkout.line_items.all():
        total += quantize_money(li.unit_price * li.quantity)
    return quantize_money(total)


def discount_eligible_amount(code: DiscountCode | None, subtotal: Decimal, now=None) -> bool:
    if not code or not code.is_active:
        return False
    now = now or timezone.now()
    if code.starts_at and now < code.starts_at:
        return False
    if code.ends_at and now > code.ends_at:
        return False
    if subtotal < quantize_money(code.minimum_subtotal or Decimal("0")):
        return False
    if code.usage_limit is not None and code.usage_count >= code.usage_limit:
        return False
    return True


def compute_discount_amount(
    subtotal: Decimal,
    code: DiscountCode | None,
    now=None,
) -> Decimal:
    if not discount_eligible_amount(code, subtotal, now=now):
        return Decimal("0.00")
    assert code is not None
    if code.discount_type == DISCOUNT_TYPE_PERCENTAGE:
        raw = subtotal * (code.value / Decimal("100"))
        if code.max_discount_amount is not None:
            raw = min(raw, code.max_discount_amount)
    else:
        raw = code.value
    return quantize_money(min(raw, subtotal))


def amount_due_before_gift_cards(checkout: Checkout, discount_amount: Decimal) -> Decimal:
    merchandise = quantize_money(line_items_subtotal(checkout) - discount_amount)
    if merchandise < Decimal("0.00"):
        merchandise = Decimal("0.00")
    return quantize_money(
        merchandise + quantize_money(checkout.shipping_total) + quantize_money(checkout.tax_total)
    )


def redistribute_gift_card_applications(checkout: Checkout) -> Decimal:
    """
    Recompute each application's amount_applied to fit current totals and balances.
    Returns total applied across gift cards.
    """
    discount_amt = compute_discount_amount(
        line_items_subtotal(checkout),
        checkout.discount_code,
    )
    due = amount_due_before_gift_cards(checkout, discount_amt)
    remaining = due

    applications = list(
        checkout.gift_card_applications.select_related("gift_card").order_by("id")
    )
    total_applied = Decimal("0.00")

    for app in applications:
        gc = app.gift_card
        if not gc.is_active:
            max_from_card = Decimal("0.00")
        elif gc.expires_at and timezone.now() > gc.expires_at:
            max_from_card = Decimal("0.00")
        else:
            max_from_card = quantize_money(gc.current_balance)

        applied = quantize_money(min(app.amount_applied, max_from_card, remaining))
        app.amount_applied = applied
        app.save(update_fields=["amount_applied", "updated_at"])
        total_applied += applied
        remaining = quantize_money(remaining - applied)

    if remaining < Decimal("0.00"):
        remaining = Decimal("0.00")

    # Remove applications that no longer apply (zero amount)
    for app in applications:
        if app.amount_applied == Decimal("0.00"):
            app.delete()

    return quantize_money(
        CheckoutGiftCardApplication.objects.filter(checkout=checkout).aggregate(
            s=Sum("amount_applied")
        )["s"]
        or Decimal("0.00")
    )


def recalculate_checkout(checkout: Checkout) -> Checkout:
    """Refresh discount_amount and gift card allocations from current lines and codes."""
    subtotal = line_items_subtotal(checkout)
    discount_amt = compute_discount_amount(subtotal, checkout.discount_code)
    checkout.discount_amount = discount_amt
    checkout.save(update_fields=["discount_amount", "updated_at"])
    redistribute_gift_card_applications(checkout)
    checkout.refresh_from_db()
    return checkout


def checkout_totals(checkout: Checkout) -> dict:
    """Computed snapshot for API responses."""
    subtotal = line_items_subtotal(checkout)
    discount_amt = quantize_money(checkout.discount_amount)
    gift_total = quantize_money(
        CheckoutGiftCardApplication.objects.filter(checkout=checkout).aggregate(
            s=Sum("amount_applied")
        )["s"]
        or Decimal("0.00")
    )
    due_before_gifts = amount_due_before_gift_cards(checkout, discount_amt)
    total = quantize_money(due_before_gifts - gift_total)
    if total < Decimal("0.00"):
        total = Decimal("0.00")
    return {
        "subtotal": str(subtotal),
        "discount_amount": str(discount_amt),
        "shipping_total": str(quantize_money(checkout.shipping_total)),
        "tax_total": str(quantize_money(checkout.tax_total)),
        "gift_card_total": str(gift_total),
        "total": str(total),
        "amount_due_before_gift_cards": str(due_before_gifts),
    }


def validate_discount_for_apply(code: DiscountCode, subtotal: Decimal) -> str | None:
    """Return error message if code cannot be applied; None if OK."""
    if not code.is_active:
        return "Discount code is not active."
    now = timezone.now()
    if code.starts_at and now < code.starts_at:
        return "Discount code is not valid yet."
    if code.ends_at and now > code.ends_at:
        return "Discount code has expired."
    if subtotal < quantize_money(code.minimum_subtotal or Decimal("0")):
        return "Cart subtotal is below the minimum for this discount."
    if code.usage_limit is not None and code.usage_count >= code.usage_limit:
        return "Discount code has reached its usage limit."
    return None


def validate_gift_card_for_apply(gift_card: GiftCard) -> str | None:
    if not gift_card.is_active:
        return "Gift card is not active."
    if gift_card.expires_at and timezone.now() > gift_card.expires_at:
        return "Gift card has expired."
    if gift_card.current_balance <= Decimal("0.00"):
        return "Gift card has no remaining balance."
    return None


@transaction.atomic
def complete_checkout(
    checkout: Checkout,
    *,
    customer=None,
    financial_status: str = ORDER_FINANCIAL_PAID,
    stripe_payment_intent_id: str = "",
) -> Order:
    """
    Finalize checkout: create order, decrement inventory, burn discount usage,
    deduct gift card balances. Caller must hold checkout with select_for_update.
    """
    recalculate_checkout(checkout)
    checkout.refresh_from_db()

    if checkout.status != CHECKOUT_STATUS_OPEN:
        raise ValueError("Checkout is not open.")

    if not checkout.line_items.exists():
        raise ValueError("Checkout has no line items.")

    totals = checkout_totals(checkout)
    subtotal = Decimal(totals["subtotal"])
    discount_amt = Decimal(totals["discount_amount"])
    gift_total = Decimal(totals["gift_card_total"])
    total = Decimal(totals["total"])

    if checkout.discount_code_id:
        code = DiscountCode.objects.select_for_update().get(pk=checkout.discount_code_id)
        if not discount_eligible_amount(code, subtotal):
            raise ValueError("Discount code is no longer valid for this checkout.")
        if compute_discount_amount(subtotal, code) != discount_amt:
            raise ValueError("Discount amount is out of date; refresh and try again.")

    line_items = list(
        checkout.line_items.select_related("variant", "variant__product").all()
    )
    for li in line_items:
        variant = ProductVariant.objects.select_for_update().get(pk=li.variant_id)
        if not variant.is_active:
            raise ValueError(f"Variant {variant.id} is not available.")
        if variant.product.deleted_at is not None:
            raise ValueError(f"Product for variant {variant.id} is no longer available.")
        if not variant.product.is_published or variant.product.status != "active":
            raise ValueError(f"Product for variant {variant.id} is not purchasable.")
        if variant.inventory_quantity < li.quantity:
            raise ValueError(
                f"Insufficient inventory for variant {variant.id} (SKU {variant.sku or 'n/a'})."
            )

    applications = list(
        checkout.gift_card_applications.select_related("gift_card").all()
    )
    for app in applications:
        gc = GiftCard.objects.select_for_update().get(pk=app.gift_card_id)
        err = validate_gift_card_for_apply(gc)
        if err:
            raise ValueError(err)
        if app.amount_applied > gc.current_balance:
            raise ValueError("Gift card balance changed; refresh checkout.")

    order = Order.objects.create(
        checkout=checkout,
        token=checkout.token,
        customer=customer,
        email=checkout.email,
        phone=checkout.phone,
        currency=checkout.currency,
        shipping_address=checkout.shipping_address or {},
        billing_address=checkout.billing_address or {},
        subtotal=subtotal,
        discount_amount=discount_amt,
        shipping_total=quantize_money(checkout.shipping_total),
        tax_total=quantize_money(checkout.tax_total),
        gift_card_total=gift_total,
        total=total,
        discount_code_snapshot=checkout.discount_code.code if checkout.discount_code else "",
        note=checkout.note,
        financial_status=financial_status,
        stripe_payment_intent_id=stripe_payment_intent_id or "",
    )

    for li in line_items:
        variant = li.variant
        line_total = quantize_money(li.unit_price * li.quantity)
        OrderLineItem.objects.create(
            order=order,
            variant=variant,
            product_title=variant.product.title,
            variant_title=variant.title,
            sku=variant.sku or "",
            quantity=li.quantity,
            unit_price=li.unit_price,
            line_total=line_total,
        )
        ProductVariant.objects.filter(pk=variant.pk).update(
            inventory_quantity=F("inventory_quantity") - li.quantity
        )

    if checkout.discount_code_id:
        DiscountCode.objects.filter(pk=checkout.discount_code_id).update(
            usage_count=F("usage_count") + 1
        )

    for app in applications:
        GiftCard.objects.filter(pk=app.gift_card_id).update(
            current_balance=F("current_balance") - app.amount_applied
        )

    checkout.status = CHECKOUT_STATUS_COMPLETED
    checkout.save(update_fields=["status", "updated_at"])

    return order
