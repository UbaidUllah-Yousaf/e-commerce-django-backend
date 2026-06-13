from decimal import Decimal

from django.db import models

from ecommerce.constants.discount import (
    DISCOUNT_TYPE_CHOICES,
    DISCOUNT_TYPE_FIXED_AMOUNT,
    DISCOUNT_TYPE_PERCENTAGE,
)
from ecommerce.validators import identifier_min_length_validator
from utils.timestamped import TimeStampedModel


class DiscountCode(TimeStampedModel):
    """Store-wide discount code (Shopify-style price rule / discount code)."""

    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        validators=[identifier_min_length_validator],
    )
    title = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default=DISCOUNT_TYPE_PERCENTAGE,
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percentage (0–100) or fixed currency amount depending on type.",
    )
    minimum_subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Caps percentage discounts; ignored for fixed amount.",
    )
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of completed checkouts; null means unlimited.",
    )
    usage_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code
