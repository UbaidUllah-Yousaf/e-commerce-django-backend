from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils.text import slugify

from ecommerce.constants.fulfillment import (
    FULFILLMENT_STATUS_FULFILLED,
    FULFILLMENT_STATUS_PARTIAL,
    FULFILLMENT_STATUS_UNFULFILLED,
    SHIPMENT_STATUS_CHOICES,
    SHIPMENT_STATUS_PENDING,
    SHIPMENT_STATUS_SUCCESS,
    SHIPMENT_TERMINAL_VOID_STATUSES,
)
from utils.timestamped import TimeStampedModel


class FulfillmentService(TimeStampedModel):
    """
    Configurable fulfillment / courier profile (Shopify-style fulfillment service).
    Assign orders to a service from admin when creating fulfillments.
    """

    name = models.CharField(max_length=255)
    courier_name = models.CharField(
        max_length=255,
        help_text="Display name shown on packing slips and tracking (e.g. DHL Express).",
    )
    carrier_code = models.CharField(
        max_length=64,
        blank=True,
        help_text="Short code for integrations (e.g. dhl, fedex, ups).",
    )
    tracking_url_template = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional URL with {tracking_number} placeholder.",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    logo = models.ImageField(upload_to="fulfillment_services/", null=True, blank=True)

    class Meta:
        ordering = ["courier_name", "name"]

    def __str__(self):
        return f"{self.courier_name} — {self.name}"

    def build_tracking_url(self, tracking_number: str) -> str:
        if not self.tracking_url_template or not tracking_number:
            return ""
        return self.tracking_url_template.replace("{tracking_number}", tracking_number)


class Fulfillment(TimeStampedModel):
    """
    One shipment for an order (order can have multiple fulfillments / packages).
    """

    order = models.ForeignKey(
        "ecommerce.Order",
        on_delete=models.CASCADE,
        related_name="fulfillments",
    )
    fulfillment_service = models.ForeignKey(
        FulfillmentService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfillments",
        help_text="Courier / fulfillment profile for this shipment.",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label (e.g. Partial shipment — accessories).",
    )
    status = models.CharField(
        max_length=20,
        choices=SHIPMENT_STATUS_CHOICES,
        default=SHIPMENT_STATUS_PENDING,
        db_index=True,
    )
    tracking_company = models.CharField(
        max_length=255,
        blank=True,
        help_text="Override carrier name on labels; defaults from fulfillment service if empty.",
    )
    tracking_number = models.CharField(max_length=255, blank=True)
    tracking_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Full tracking URL; if empty, may be derived from the service template.",
    )
    notify_customer = models.BooleanField(default=False)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    logistics_shipment = models.ForeignKey(
        "logistics.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_fulfillments",
        help_text="Logistics pipeline shipment; status and tracking sync from here.",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        pk = self.pk or "—"
        svc = self.fulfillment_service.courier_name if self.fulfillment_service else "Manual"
        return f"Fulfillment {pk} ({svc}) — Order {self.order_id}"

    def effective_tracking_company(self) -> str:
        if self.tracking_company:
            return self.tracking_company
        if self.fulfillment_service:
            return self.fulfillment_service.courier_name
        return ""

    def effective_tracking_url(self) -> str:
        if self.tracking_url:
            return self.tracking_url
        if self.fulfillment_service and self.tracking_number:
            return self.fulfillment_service.build_tracking_url(self.tracking_number)
        return ""

    def tracking_fingerprint(self) -> tuple[str, str, str, int | None]:
        """
        Comparable tuple for “same tracking details” across fulfillments:
        effective carrier label, tracking number, effective URL, fulfillment service id (or None).
        """
        company = (self.effective_tracking_company() or "").strip().lower()
        number = (self.tracking_number or "").strip().lower()
        url = (self.effective_tracking_url() or "").strip()
        return (company, number, url, self.fulfillment_service_id)


def _allocated_quantity_for_order_line(
    order_line_item_id: int,
    exclude_fulfillment_line_item_id: int | None = None,
) -> int:
    qs = FulfillmentLineItem.objects.filter(
        order_line_item_id=order_line_item_id,
    ).exclude(fulfillment__status__in=SHIPMENT_TERMINAL_VOID_STATUSES)
    if exclude_fulfillment_line_item_id:
        qs = qs.exclude(pk=exclude_fulfillment_line_item_id)
    agg = qs.aggregate(s=Sum("quantity"))
    return int(agg["s"] or 0)


def _fulfilled_success_quantity_for_order_line(order_line_item_id: int) -> int:
    qs = FulfillmentLineItem.objects.filter(
        order_line_item_id=order_line_item_id,
        fulfillment__status=SHIPMENT_STATUS_SUCCESS,
    )
    agg = qs.aggregate(s=Sum("quantity"))
    return int(agg["s"] or 0)


def remaining_quantity_to_allocate(order_line_item_id: int) -> int:
    """
    Units on an order line not yet tied to a fulfillment (pending/open/in_transit/success).
    Cancelled/error/failure fulfillments do not consume this budget.
    """
    from ecommerce.models.checkout import OrderLineItem

    oli = OrderLineItem.objects.filter(pk=order_line_item_id).first()
    if not oli:
        return 0
    allocated = _allocated_quantity_for_order_line(order_line_item_id)
    return max(0, oli.quantity - allocated)


def _compute_order_line_fulfillment_state(order_line_item) -> str:
    """Derive line fulfillment from success fulfillment quantities (not the stored field)."""
    if not order_line_item.pk:
        return FULFILLMENT_STATUS_UNFULFILLED
    fulfilled = _fulfilled_success_quantity_for_order_line(order_line_item.pk)
    if fulfilled <= 0:
        return FULFILLMENT_STATUS_UNFULFILLED
    if fulfilled >= order_line_item.quantity:
        return FULFILLMENT_STATUS_FULFILLED
    return FULFILLMENT_STATUS_PARTIAL


def _compute_order_fulfillment_state(order) -> str:
    """
    Derive order fulfillment from line items + successful shipments + tracking fingerprint.
    """
    lines = list(order.line_items.order_by("id").all())
    if not lines:
        return FULFILLMENT_STATUS_UNFULFILLED

    any_success_qty = False
    all_complete = True
    for li in lines:
        fulfilled = _fulfilled_success_quantity_for_order_line(li.pk)
        if fulfilled > 0:
            any_success_qty = True
        if fulfilled < li.quantity:
            all_complete = False

    if not any_success_qty:
        return FULFILLMENT_STATUS_UNFULFILLED
    if not all_complete:
        return FULFILLMENT_STATUS_PARTIAL

    success_with_lines = (
        Fulfillment.objects.filter(order=order, status=SHIPMENT_STATUS_SUCCESS)
        .prefetch_related("line_items")
    )
    fps = set()
    for f in success_with_lines:
        if f.line_items.exists():
            fps.add(f.tracking_fingerprint())

    if len(fps) <= 1:
        return FULFILLMENT_STATUS_FULFILLED
    return FULFILLMENT_STATUS_PARTIAL


def recompute_fulfillment_statuses_for_order(order_id: int) -> None:
    """Persist fulfillment_status on Order and all its OrderLineItems."""
    from ecommerce.models.checkout import Order, OrderLineItem

    order = (
        Order.objects.prefetch_related("line_items")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return

    for oli in order.line_items.all():
        st = _compute_order_line_fulfillment_state(oli)
        OrderLineItem.objects.filter(pk=oli.pk).exclude(fulfillment_status=st).update(
            fulfillment_status=st
        )

    order_st = _compute_order_fulfillment_state(order)
    Order.objects.filter(pk=order_id).exclude(fulfillment_status=order_st).update(
        fulfillment_status=order_st
    )


def get_order_line_fulfillment_state(order_line_item) -> str:
    """Return persisted line fulfillment_status (fresh from DB when saved)."""
    if not order_line_item.pk:
        return _compute_order_line_fulfillment_state(order_line_item)
    from ecommerce.models.checkout import OrderLineItem

    return OrderLineItem.objects.values_list("fulfillment_status", flat=True).get(
        pk=order_line_item.pk
    )


def get_order_fulfillment_state(order) -> str:
    """Return persisted order fulfillment_status (fresh from DB when saved)."""
    if not order.pk:
        return _compute_order_fulfillment_state(order)
    from ecommerce.models.checkout import Order

    return Order.objects.values_list("fulfillment_status", flat=True).get(pk=order.pk)


def fulfillment_remaining_lines(order) -> list[dict]:
    """Per–order-line snapshot for admin / storefront fulfillment UIs (Shopify-style)."""
    rows: list[dict] = []
    for oli in order.line_items.order_by("id").all():
        rows.append(
            {
                "order_line_item": oli.pk,
                "product_title": oli.product_title,
                "variant_title": oli.variant_title,
                "sku": oli.sku,
                "quantity_ordered": oli.quantity,
                "quantity_delivered_success": _fulfilled_success_quantity_for_order_line(oli.pk),
                "quantity_remaining_allocatable": remaining_quantity_to_allocate(oli.pk),
                "fulfillment_status": oli.fulfillment_status,
            }
        )
    return rows


class FulfillmentLineItem(TimeStampedModel):
    """Quantity of an order line included in a fulfillment."""

    fulfillment = models.ForeignKey(
        Fulfillment,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    order_line_item = models.ForeignKey(
        "ecommerce.OrderLineItem",
        on_delete=models.CASCADE,
        related_name="fulfillment_line_items",
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.fulfillment_id} line {self.order_line_item_id} × {self.quantity}"

    def clean(self):
        super().clean()
        if self.order_line_item_id and self.fulfillment_id:
            if self.order_line_item.order_id != self.fulfillment.order_id:
                raise ValidationError(
                    {"order_line_item": "Line item must belong to the same order as the fulfillment."}
                )
        if self.quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})
        if self.order_line_item_id:
            allocated_excl = _allocated_quantity_for_order_line(
                self.order_line_item_id,
                exclude_fulfillment_line_item_id=self.pk,
            )
            remaining = self.order_line_item.quantity - allocated_excl
            if self.quantity > remaining:
                raise ValidationError(
                    {
                        "quantity": (
                            f"Cannot fulfill {self.quantity} units; only {remaining} remaining "
                            "for this order line (across active fulfillments)."
                        )
                    }
                )

