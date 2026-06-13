import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from ecommerce.constants.checkout import (
    CHECKOUT_STATUS_CHOICES,
    CHECKOUT_STATUS_OPEN,
    ORDER_FINANCIAL_CHOICES,
    ORDER_FINANCIAL_PENDING,
)
from ecommerce.constants.fulfillment import (
    FULFILLMENT_STATUS_CHOICES,
    FULFILLMENT_STATUS_UNFULFILLED,
)
from ecommerce.models.discount import DiscountCode
from ecommerce.models.gift_card import GiftCard
from ecommerce.models.product import ProductVariant
from utils.timestamped import TimeStampedModel


class Checkout(TimeStampedModel):
    """
    Draft checkout session (Shopify Checkout–style): line items, addresses,
    discount code, gift cards, shipping/tax, then complete → Order.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=20,
        choices=CHECKOUT_STATUS_CHOICES,
        default=CHECKOUT_STATUS_OPEN,
        db_index=True,
    )
    note = models.TextField(blank=True)

    shipping_address = models.JSONField(default=dict, blank=True)
    billing_address = models.JSONField(default=dict, blank=True)
    billing_same_as_shipping = models.BooleanField(default=True)

    shipping_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkouts",
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    gift_cards = models.ManyToManyField(
        GiftCard,
        through="CheckoutGiftCardApplication",
        related_name="checkouts",
        blank=True,
    )

    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Stripe Checkout Session id (cs_…) while payment is in progress.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Checkout {self.token}"


class OrderNumberSequence(models.Model):
    """
    Single-row counter for sequential customer-facing order numbers (Shopify order_number).

    Row pk=1 only. ``next_order_number`` is the value to assign to the *next* new order.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_order_number = models.PositiveIntegerField(
        default=1000,
        help_text="Next value assigned to a new order; incremented after each allocation.",
    )

    class Meta:
        verbose_name = "Order number sequence"

    def __str__(self):
        return f"Next order number: {self.next_order_number}"


class CheckoutLineItem(TimeStampedModel):
    checkout = models.ForeignKey(
        Checkout,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="checkout_line_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["checkout", "variant"],
                name="unique_checkout_variant_line",
            ),
        ]

    def __str__(self):
        return f"{self.checkout_id} × {self.variant_id}"


class CheckoutGiftCardApplication(TimeStampedModel):
    """Pending allocation of gift card balance against an open checkout."""

    checkout = models.ForeignKey(
        Checkout,
        on_delete=models.CASCADE,
        related_name="gift_card_applications",
    )
    gift_card = models.ForeignKey(
        GiftCard,
        on_delete=models.PROTECT,
        related_name="checkout_applications",
    )
    amount_applied = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["checkout", "gift_card"],
                name="unique_checkout_gift_card",
            ),
        ]


class Order(TimeStampedModel):
    """Completed sale created from a checkout."""

    checkout = models.OneToOneField(
        Checkout,
        on_delete=models.PROTECT,
        related_name="order",
    )
    order_number = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        help_text="Sequential customer-facing number (Shopify order_number).",
    )
    name = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Display name for storefronts (Shopify name), e.g. #1001.",
    )
    token = models.UUIDField(db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Set when checkout is completed by an authenticated customer.",
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    currency = models.CharField(max_length=3, default="USD")

    shipping_address = models.JSONField(default=dict, blank=True)
    billing_address = models.JSONField(default=dict, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2)
    gift_card_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    discount_code_snapshot = models.CharField(max_length=64, blank=True)
    financial_status = models.CharField(
        max_length=20,
        choices=ORDER_FINANCIAL_CHOICES,
        default=ORDER_FINANCIAL_PENDING,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Stripe PaymentIntent id (pi_…) after successful payment.",
    )
    fulfillment_status = models.CharField(
        max_length=20,
        choices=FULFILLMENT_STATUS_CHOICES,
        default=FULFILLMENT_STATUS_UNFULFILLED,
        db_index=True,
        help_text="Denormalized from fulfillments; editable in admin; recomputed when fulfillments change.",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self._state.adding:
            from ecommerce.services.order_numbers import allocate_order_number, format_order_name

            if self.order_number is None:
                self.order_number = allocate_order_number()
            if not self.name:
                self.name = format_order_name(self.order_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.name} ({self.token})"


class OrderLineItem(TimeStampedModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="order_line_items",
    )
    product_title = models.CharField(max_length=255)
    variant_title = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    fulfillment_status = models.CharField(
        max_length=20,
        choices=FULFILLMENT_STATUS_CHOICES,
        default=FULFILLMENT_STATUS_UNFULFILLED,
        db_index=True,
        help_text="Denormalized from fulfillments; editable in admin; recomputed when fulfillments change.",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"OrderLine {self.order_id} {self.variant_id}"
