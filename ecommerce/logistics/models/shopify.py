from django.db import models

from utils.timestamped import TimeStampedModel


class ShopifyConfiguration(TimeStampedModel):
    shop_name = models.CharField(max_length=255)
    shop_domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="e.g. my-store.myshopify.com",
    )
    access_token = models.TextField(help_text="Admin API access token")
    webhook_secret = models.CharField(
        max_length=255,
        help_text="Shared secret for HMAC verification of Shopify webhooks",
    )
    api_version = models.CharField(max_length=32, default="2024-10")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Shopify store"
        verbose_name_plural = "Shopify stores"
        ordering = ["shop_name"]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.shop_name} ({self.shop_domain}) [{status}]"

    @property
    def admin_api_base_url(self) -> str:
        domain = self.shop_domain.strip().rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/admin/api/{self.api_version}"
