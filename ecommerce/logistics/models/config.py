from django.db import models


class FulfillmentConfiguration(models.Model):
    """Singleton store-wide logistics settings (pk=1)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    auto_fulfill_enabled = models.BooleanField(
        default=True,
        help_text="Automatically create fulfillments after Quiqup shipment.",
    )
    default_fallback_courier = models.ForeignKey(
        "logistics.CourierConfiguration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Used when no city rule matches.",
    )
    cod_enabled = models.BooleanField(
        default=True,
        help_text="Treat pending-payment ecommerce orders as COD when applicable.",
    )
    tracking_sync_enabled = models.BooleanField(
        default=True,
        help_text="Push tracking updates to Shopify and ecommerce fulfillments.",
    )
    ingest_api_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bearer token for POST /api/v1/logistics/orders/ingest/",
    )
    quiqup_webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional secret to verify Quiqup webhook signatures.",
    )
    max_retry_count = models.PositiveSmallIntegerField(default=5)

    class Meta:
        verbose_name = "Fulfillment configuration"
        verbose_name_plural = "Fulfillment configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    def __str__(self):
        return "Fulfillment configuration"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
