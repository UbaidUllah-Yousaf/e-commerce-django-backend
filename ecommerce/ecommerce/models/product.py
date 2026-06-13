from decimal import Decimal

from django.db import models
from django.utils.html import strip_tags

from ecommerce.constants.product import (
    PRODUCT_PUBLISHED_SCOPE_CHOICES,
    PRODUCT_PUBLISHED_SCOPE_WEB,
    PRODUCT_STATUS_CHOICES,
    PRODUCT_STATUS_DRAFT,
)

from ecommerce.models.collection import Collection
from ecommerce.models.tag import Tag
from utils.handle_uniqueness import unique_active_handle
from utils.softdelete import SoftDeleteModel
from utils.timestamped import TimeStampedModel


class Product(SoftDeleteModel, TimeStampedModel):
    title = models.CharField(max_length=255)
    handle = models.SlugField(blank=True)

    # Shopify Admin: body_html (rich text). description holds plain text (search, excerpts).
    body_html = models.TextField(blank=True)
    description = models.TextField(blank=True)

    collection = models.ForeignKey(
        Collection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    tags = models.ManyToManyField(
        Tag,
    )

    featured_image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True
    )

    vendor = models.CharField(max_length=255, blank=True)
    product_type = models.CharField(max_length=255, blank=True)

    # Shopify Standard Product Taxonomy path (e.g. "Apparel & Accessories > Clothing > …").
    product_category = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=PRODUCT_STATUS_CHOICES,
        default=PRODUCT_STATUS_DRAFT,
    )

    is_published = models.BooleanField(default=False)

    published_scope = models.CharField(
        max_length=20,
        choices=PRODUCT_PUBLISHED_SCOPE_CHOICES,
        default=PRODUCT_PUBLISHED_SCOPE_WEB,
        help_text="Mirrors Shopify published_scope for the online channel.",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the product became available on the storefront (Shopify published_at).",
    )

    template_suffix = models.CharField(
        max_length=255,
        blank=True,
        help_text="Shopify theme template suffix (optional).",
    )

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)

    gift_card = models.BooleanField(
        default=False,
        help_text="Shopify product gift_card flag.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["handle"],
                condition=models.Q(deleted_at__isnull=True),
                name="ecommerce_product_unique_handle_active",
            ),
        ]

    def save(self, *args, **kwargs):
        handle_max = self._meta.get_field("handle").max_length or 50
        self.handle = unique_active_handle(
            Product,
            raw_handle=self.handle or "",
            raw_title=self.title or "",
            exclude_pk=self.pk,
            max_length=handle_max,
        )
        if self.body_html and not self.description:
            self.description = strip_tags(self.body_html)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def min_price(self):
        variant = self.variants.order_by("price").first()
        return variant.price if variant else Decimal("0.00")

    @property
    def max_price(self):
        variant = self.variants.order_by("-price").first()
        return variant.price if variant else Decimal("0.00")


# -----------------------------------
# PRODUCT OPTION MODEL
# Example:
# Size, Color
# -----------------------------------

class ProductOption(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="options"
    )

    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("product", "name")

    def __str__(self):
        return f"{self.product.title} - {self.name}"


# -----------------------------------
# PRODUCT OPTION VALUE
# Example:
# Red, Blue, XL, Small
# -----------------------------------

class ProductOptionValue(TimeStampedModel):
    option = models.ForeignKey(
        ProductOption,
        on_delete=models.CASCADE,
        related_name="values"
    )

    value = models.CharField(max_length=100)

    class Meta:
        unique_together = ("option", "value")

    def __str__(self):
        return self.value


# -----------------------------------
# PRODUCT VARIANT MODEL
# -----------------------------------

class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants"
    )

    title = models.CharField(max_length=255)

    sku = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    cost_per_item = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    inventory_quantity = models.PositiveIntegerField(default=0)

    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(default=True)

    image = models.ImageField(
        upload_to="variants/",
        blank=True,
        null=True
    )

    option_values = models.ManyToManyField(
        ProductOptionValue,
        blank=True,
        related_name="variants"
    )

    class Meta:
        ordering = ["product", "title"]

    def __str__(self):
        return f"{self.product.title} - {self.title}"
