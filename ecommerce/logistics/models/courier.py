from django.db import models

from utils.timestamped import TimeStampedModel


class CourierConfiguration(TimeStampedModel):
    courier_name = models.CharField(max_length=255, unique=True)
    api_credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional per-courier credentials (JSON).",
    )
    supported_cities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of city names this courier supports. Empty = all cities.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["courier_name"]
        verbose_name = "Courier configuration"
        verbose_name_plural = "Courier configurations"

    def __str__(self):
        return self.courier_name
