"""Discount code value-type choices (mirrors ``DiscountCode.discount_type``)."""

DISCOUNT_TYPE_PERCENTAGE = "percentage"
DISCOUNT_TYPE_FIXED_AMOUNT = "fixed_amount"
DISCOUNT_TYPE_CHOICES = (
    (DISCOUNT_TYPE_PERCENTAGE, "Percentage"),
    (DISCOUNT_TYPE_FIXED_AMOUNT, "Fixed amount"),
)
