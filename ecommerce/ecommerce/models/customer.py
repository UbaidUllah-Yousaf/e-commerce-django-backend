from django.conf import settings
from django.db import models

from utils.timestamped import TimeStampedModel


class CustomerProfile(TimeStampedModel):
    """
    Extended customer record (Shopify Customer–style metadata)
    linked to Django auth User.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    accepts_marketing = models.BooleanField(default=False)
    tax_exempt = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CustomerProfile({self.user_id})"


class CustomerAddress(TimeStampedModel):
    """
    Saved shipping/billing address (aligned with Shopify CustomerAddress fields).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_addresses",
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    company = models.CharField(max_length=255, blank=True)
    address1 = models.CharField(max_length=255)
    address2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    province_code = models.CharField(
        max_length=32,
        blank=True,
        help_text="State/province code (e.g. CA, NY).",
    )
    country_code = models.CharField(
        max_length=2,
        help_text="ISO 3166-1 alpha-2 country code.",
    )
    zip = models.CharField(max_length=32)
    phone = models.CharField(max_length=32, blank=True)
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.address1}, {self.city} ({self.user_id})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default_shipping:
            CustomerAddress.objects.filter(user_id=self.user_id).exclude(pk=self.pk).update(
                is_default_shipping=False
            )
        if self.is_default_billing:
            CustomerAddress.objects.filter(user_id=self.user_id).exclude(pk=self.pk).update(
                is_default_billing=False
            )
