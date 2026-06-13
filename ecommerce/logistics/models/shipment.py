import uuid

from django.db import models

from logistics.constants import (
    LOGISTICS_STATUS_PENDING,
    LOGISTICS_STATUS_CHOICES,
    PROCESSING_RECEIVED,
    PROCESSING_STATE_CHOICES,
    SOURCE_PLATFORM_CHOICES,
)
from utils.timestamped import TimeStampedModel


class Shipment(TimeStampedModel):
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    source_platform = models.CharField(max_length=32, choices=SOURCE_PLATFORM_CHOICES, db_index=True)
    shop = models.ForeignKey(
        "logistics.ShopifyConfiguration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )
    ecommerce_order = models.ForeignKey(
        "ecommerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logistics_shipments",
    )
    external_order_id = models.CharField(max_length=64, db_index=True)
    order_number = models.CharField(max_length=64, blank=True, db_index=True)
    customer_payload = models.JSONField(default=dict, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)
    line_items = models.JSONField(default=list, blank=True)
    city = models.CharField(max_length=128, blank=True, db_index=True)
    cod_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    courier_name = models.CharField(max_length=255, blank=True, db_index=True)
    service_type = models.CharField(max_length=64, blank=True)
    courier_override = models.CharField(
        max_length=255,
        blank=True,
        help_text="Admin override; takes precedence over city rules.",
    )
    quiqup_shipment_id = models.CharField(max_length=128, blank=True, db_index=True)
    tracking_number = models.CharField(max_length=255, blank=True, db_index=True)
    tracking_url = models.URLField(max_length=500, blank=True)
    shipment_status = models.CharField(
        max_length=32,
        choices=LOGISTICS_STATUS_CHOICES,
        default=LOGISTICS_STATUS_PENDING,
        db_index=True,
    )
    processing_state = models.CharField(
        max_length=32,
        choices=PROCESSING_STATE_CHOICES,
        default=PROCESSING_RECEIVED,
        db_index=True,
    )
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    last_celery_task_id = models.CharField(max_length=255, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_platform", "external_order_id"]),
        ]

    def __str__(self):
        return f"Shipment {self.order_number or self.external_order_id} ({self.shipment_status})"


class ShipmentStatusHistory(TimeStampedModel):
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    status = models.CharField(max_length=32, choices=LOGISTICS_STATUS_CHOICES)
    source = models.CharField(max_length=32)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Shipment status history"

    def __str__(self):
        return f"{self.shipment_id}: {self.status}"


class WebhookLog(TimeStampedModel):
    shop = models.ForeignKey(
        "logistics.ShopifyConfiguration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_logs",
    )
    source_platform = models.CharField(max_length=32, choices=SOURCE_PLATFORM_CHOICES)
    event_type = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Webhook {self.source_platform} {self.event_type} processed={self.processed}"
