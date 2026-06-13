"""
Checkout session and order financial status choices.

These values are shared with ``ecommerce.models.checkout``; import from here in services,
serializers, and tests instead of attaching choice tuples to model classes.
"""

CHECKOUT_STATUS_OPEN = "open"
CHECKOUT_STATUS_COMPLETED = "completed"
CHECKOUT_STATUS_CANCELLED = "cancelled"
CHECKOUT_STATUS_CHOICES = (
    (CHECKOUT_STATUS_OPEN, "Open"),
    (CHECKOUT_STATUS_COMPLETED, "Completed"),
    (CHECKOUT_STATUS_CANCELLED, "Cancelled"),
)

ORDER_FINANCIAL_PENDING = "pending"
ORDER_FINANCIAL_PAID = "paid"
ORDER_FINANCIAL_CHOICES = (
    (ORDER_FINANCIAL_PENDING, "Pending"),
    (ORDER_FINANCIAL_PAID, "Paid"),
)
