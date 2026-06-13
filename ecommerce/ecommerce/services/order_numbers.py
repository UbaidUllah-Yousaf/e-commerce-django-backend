"""Customer-facing order numbers and names (Shopify-style: order_number + name e.g. #1001)."""

from django.conf import settings


def format_order_name(order_number: int) -> str:
    prefix = getattr(settings, "ECOMMERCE_ORDER_NAME_PREFIX", "#")
    return f"{prefix}{order_number}"


def allocate_order_number() -> int:
    """
    Return the next sequential order_number and advance the counter.

    Caller must run inside transaction.atomic() with the same lock scope as order creation
    (e.g. complete_checkout already holds checkout FOR UPDATE).
    """
    from ecommerce.models.checkout import OrderNumberSequence

    start = int(getattr(settings, "ECOMMERCE_FIRST_ORDER_NUMBER", 1000))
    seq, _ = OrderNumberSequence.objects.select_for_update().get_or_create(
        pk=1,
        defaults={"next_order_number": start},
    )
    number = seq.next_order_number
    seq.next_order_number = number + 1
    seq.save(update_fields=["next_order_number"])
    return number
