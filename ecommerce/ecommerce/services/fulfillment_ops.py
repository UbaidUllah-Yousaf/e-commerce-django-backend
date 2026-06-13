"""
Create order fulfillments (Shopify-style): complete remaining, partial lines, manual carrier.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from ecommerce.constants.fulfillment import (
    FULFILLMENT_CREATE_SCOPE_COMPLETE,
    FULFILLMENT_CREATE_SCOPE_PARTIAL,
    SHIPMENT_STATUS_CHOICES,
    SHIPMENT_STATUS_IN_TRANSIT,
    SHIPMENT_STATUS_SUCCESS,
)
from ecommerce.models.checkout import Order, OrderLineItem
from ecommerce.models.fulfillment import (
    Fulfillment,
    FulfillmentLineItem,
    FulfillmentService,
    remaining_quantity_to_allocate,
)


class FulfillmentCreateError(ValueError):
    pass


def _resolve_line_specs(
    order: Order,
    scope: str,
    line_items: list[dict[str, Any]] | None,
) -> list[tuple[OrderLineItem, int]]:
    specs: list[tuple[OrderLineItem, int]] = []
    if scope == FULFILLMENT_CREATE_SCOPE_COMPLETE:
        for oli in order.line_items.order_by("id").all():
            rem = remaining_quantity_to_allocate(oli.pk)
            if rem > 0:
                specs.append((oli, rem))
        if not specs:
            raise FulfillmentCreateError(
                "No remaining quantity to fulfill on this order (complete scope)."
            )
        return specs

    if scope != FULFILLMENT_CREATE_SCOPE_PARTIAL:
        raise FulfillmentCreateError(
            f"scope must be {FULFILLMENT_CREATE_SCOPE_COMPLETE!r} or {FULFILLMENT_CREATE_SCOPE_PARTIAL!r}."
        )

    if not line_items:
        raise FulfillmentCreateError(
            "For partial fulfillment, provide line_items with order_line_item and quantity."
        )

    seen: set[int] = set()
    for row in line_items:
        oid = int(row["order_line_item"])
        qty = int(row["quantity"])
        if oid in seen:
            raise FulfillmentCreateError(f"Duplicate order_line_item {oid} in line_items.")
        seen.add(oid)
        if qty < 1:
            raise FulfillmentCreateError("Each line_items quantity must be at least 1.")
        try:
            oli = order.line_items.get(pk=oid)
        except OrderLineItem.DoesNotExist as exc:
            raise FulfillmentCreateError(
                f"Order line {oid} does not belong to this order."
            ) from exc
        rem = remaining_quantity_to_allocate(oli.pk)
        if qty > rem:
            raise FulfillmentCreateError(
                f"Cannot fulfill {qty} units on line {oid}; only {rem} remaining."
            )
        specs.append((oli, qty))
    return specs


@transaction.atomic
def create_order_fulfillment(
    order: Order,
    *,
    scope: str,
    manual: bool,
    fulfillment_service: FulfillmentService | None,
    name: str,
    notify_customer: bool,
    tracking_company: str,
    tracking_number: str,
    tracking_url: str,
    status: str,
    line_items: list[dict[str, Any]] | None,
) -> Fulfillment:
    """
    Create one Fulfillment + FulfillmentLineItems.

    * scope=complete — all remaining allocatable quantity on every order line.
    * scope=partial — explicit line_items: [{order_line_item, quantity}, ...].
    * manual=True — no fulfillment_service (Shopify manual fulfillment); tracking optional.
    """
    Order.objects.select_for_update(of=("self",)).filter(pk=order.pk).first()
    order.refresh_from_db()

    if manual:
        fulfillment_service = None

    svc = fulfillment_service
    if svc and not svc.is_active:
        raise FulfillmentCreateError("Fulfillment service is not active.")

    valid_status = {c[0] for c in SHIPMENT_STATUS_CHOICES}
    if status not in valid_status:
        raise FulfillmentCreateError("Invalid fulfillment status.")

    specs = _resolve_line_specs(order, scope, line_items)

    now = timezone.now()
    shipped_at = None
    delivered_at = None
    if status == SHIPMENT_STATUS_SUCCESS:
        shipped_at = now
        delivered_at = now
    elif status == SHIPMENT_STATUS_IN_TRANSIT:
        shipped_at = now

    fulfillment = Fulfillment.objects.create(
        order=order,
        fulfillment_service=svc,
        name=name[:255] if name else "",
        status=status,
        tracking_company=tracking_company[:255] if tracking_company else "",
        tracking_number=tracking_number[:255] if tracking_number else "",
        tracking_url=tracking_url[:500] if tracking_url else "",
        notify_customer=notify_customer,
        shipped_at=shipped_at,
        delivered_at=delivered_at,
    )

    for oli, qty in specs:
        line = FulfillmentLineItem(
            fulfillment=fulfillment,
            order_line_item=oli,
            quantity=qty,
        )
        line.full_clean()
        line.save()

    return fulfillment
