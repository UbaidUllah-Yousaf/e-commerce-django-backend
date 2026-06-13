from django.db import models


class CheckoutPaymentSettings(models.Model):
    """
    Store-wide checkout payment options (single row, pk=1).

    Managed in Django admin under Checkout → Payment settings.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    stripe_checkout_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Allow Stripe Checkout for paid carts. Also set STRIPE_SECRET_KEY and "
            "STRIPE_PUBLISHABLE_KEY in ecommerce/.env (see .env.example)."
        ),
    )
    allow_cod_complete = models.BooleanField(
        default=False,
        verbose_name="Allow cash on delivery (COD)",
        help_text=(
            "When enabled, customers can place paid orders via "
            "POST /checkouts/{id}/complete/ without Stripe (financial_status: pending)."
        ),
    )
    default_success_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=(
            "Default Stripe success redirect if the storefront omits success_url. "
            "Must include {CHECKOUT_SESSION_ID}."
        ),
    )
    default_cancel_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Default Stripe cancel redirect if the storefront omits cancel_url.",
    )
    checkout_payment_note = models.TextField(
        blank=True,
        help_text="Internal note for staff (not exposed on the storefront API).",
    )

    class Meta:
        verbose_name = "Checkout payment settings"
        verbose_name_plural = "Checkout payment settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    def __str__(self):
        return "Checkout payment settings"
