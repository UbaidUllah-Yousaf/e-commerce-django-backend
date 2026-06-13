from django.db import models

from utils.timestamped import TimeStampedModel


class CityFulfillmentRule(TimeStampedModel):
    city_name = models.CharField(
        max_length=128,
        db_index=True,
        help_text="City to match (case-insensitive). Use * for fallback.",
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower number = higher priority.",
    )
    courier_name = models.CharField(max_length=255)
    service_type = models.CharField(
        max_length=64,
        help_text="Quiqup service_kind (e.g. partner_next_day).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["priority", "city_name"]
        verbose_name = "City fulfillment rule"
        verbose_name_plural = "City fulfillment rules"

    def __str__(self):
        return f"{self.city_name} (p{self.priority}) → {self.courier_name}"
