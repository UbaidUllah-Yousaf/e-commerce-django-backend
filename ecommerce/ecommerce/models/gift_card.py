from decimal import Decimal

from django.db import models

from ecommerce.validators import identifier_min_length_validator
from utils.timestamped import TimeStampedModel


class GiftCard(TimeStampedModel):
    """Gift card with redeemable balance (balance deducted on checkout completion)."""

    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        validators=[identifier_min_length_validator],
    )
    initial_balance = models.DecimalField(max_digits=10, decimal_places=2)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.current_balance is None:
            self.current_balance = self.initial_balance
        super().save(*args, **kwargs)
