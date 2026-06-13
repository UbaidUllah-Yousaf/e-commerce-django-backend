"""django-import-export resources for Django admin CSV / XLSX import and export."""

from __future__ import annotations

from django.utils.text import slugify
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from ecommerce.models.collection import Collection
from ecommerce.models.discount import DiscountCode
from ecommerce.models.gift_card import GiftCard
from ecommerce.models.product import Product, ProductVariant
from ecommerce.models.tag import Tag


class AllObjectsForeignKeyWidget(ForeignKeyWidget):
    """Resolve FK via ``all_objects`` so soft-deleted catalog rows match on import."""

    def get_queryset(self, value, row, *args, **kwargs):
        return self.model.all_objects.all()


def _row_get(row, *keys: str):
    """First non-empty cell for any of the given header keys (import row is dict-like)."""
    if row is None:
        return None
    getter = row.get if hasattr(row, "get") else lambda k: row[k] if k in row else None
    for key in keys:
        try:
            val = getter(key)
        except (KeyError, TypeError, IndexError):
            val = None
        if val is not None and str(val).strip() != "":
            return val
    return None


class TagResource(resources.ModelResource):
    class Meta:
        model = Tag
        # Header check: only "id" is optional; matching uses id or name below.
        import_id_fields = ["id"]
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def get_instance(self, instance_loader, row):
        row = row or {}
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return Tag.objects.get(pk=int(rid))
            except (ValueError, TypeError, Tag.DoesNotExist):
                pass
        name = _row_get(row, "name", "Name", "Tag", "tag")
        if name is None:
            return None
        return Tag.objects.filter(name=str(name).strip()[:100]).first()


class CollectionResource(resources.ModelResource):
    class Meta:
        model = Collection
        import_id_fields = ["id"]
        fields = (
            "id",
            "handle",
            "title",
            "description",
            "is_active",
            "deleted_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_queryset(self):
        return Collection.all_objects.all()

    def get_instance(self, instance_loader, row):
        row = row or {}
        qs = self.get_queryset()
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return qs.get(pk=int(rid))
            except (ValueError, TypeError, Collection.DoesNotExist):
                pass
        raw = _row_get(row, "handle", "Handle", "URL handle", "URL Handle")
        if raw is None:
            return None
        h = slugify(str(raw).strip())
        if not h:
            return None
        return qs.filter(handle=h, deleted_at__isnull=True).first()


class ProductResource(resources.ModelResource):
    collection = fields.Field(
        column_name="collection_handle",
        attribute="collection",
        widget=AllObjectsForeignKeyWidget(Collection, "handle"),
    )
    tags = fields.Field(
        column_name="tags",
        attribute="tags",
        widget=ManyToManyWidget(Tag, field="name", separator=";"),
    )

    class Meta:
        model = Product
        import_id_fields = ["id"]
        fields = (
            "id",
            "handle",
            "title",
            "body_html",
            "description",
            "vendor",
            "product_type",
            "product_category",
            "status",
            "is_published",
            "published_scope",
            "published_at",
            "template_suffix",
            "seo_title",
            "seo_description",
            "gift_card",
            "deleted_at",
            "collection",
            "tags",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        # featured_image omitted — use admin or API for images.

    def get_queryset(self):
        return Product.all_objects.all()

    def get_instance(self, instance_loader, row):
        row = row or {}
        qs = self.get_queryset()
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return qs.get(pk=int(rid))
            except (ValueError, TypeError, Product.DoesNotExist):
                pass
        raw = _row_get(row, "handle", "Handle", "URL handle", "URL Handle")
        if raw is None:
            return None
        h = slugify(str(raw).strip())
        if not h:
            return None
        return qs.filter(handle=h, deleted_at__isnull=True).first()


class ProductVariantResource(resources.ModelResource):
    product = fields.Field(
        column_name="product_handle",
        attribute="product",
        widget=AllObjectsForeignKeyWidget(Product, "handle"),
    )

    class Meta:
        model = ProductVariant
        import_id_fields = ["id"]
        fields = (
            "id",
            "product",
            "title",
            "sku",
            "barcode",
            "price",
            "compare_at_price",
            "cost_per_item",
            "inventory_quantity",
            "weight",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_instance(self, instance_loader, row):
        row = row or {}
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return ProductVariant.objects.get(pk=int(rid))
            except (ValueError, TypeError, ProductVariant.DoesNotExist):
                pass
        sku = _row_get(row, "sku", "SKU", "Variant SKU")
        if sku is None:
            return None
        return ProductVariant.objects.filter(sku=str(sku).strip()[:100]).first()


class DiscountCodeResource(resources.ModelResource):
    class Meta:
        model = DiscountCode
        import_id_fields = ["id"]
        fields = (
            "id",
            "code",
            "title",
            "discount_type",
            "value",
            "minimum_subtotal",
            "max_discount_amount",
            "usage_limit",
            "usage_count",
            "starts_at",
            "ends_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_instance(self, instance_loader, row):
        row = row or {}
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return DiscountCode.objects.get(pk=int(rid))
            except (ValueError, TypeError, DiscountCode.DoesNotExist):
                pass
        code = _row_get(row, "code", "Code")
        if code is None:
            return None
        return DiscountCode.objects.filter(code=str(code).strip()[:64]).first()


class GiftCardResource(resources.ModelResource):
    class Meta:
        model = GiftCard
        import_id_fields = ["id"]
        fields = (
            "id",
            "code",
            "initial_balance",
            "current_balance",
            "currency",
            "expires_at",
            "is_active",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_instance(self, instance_loader, row):
        row = row or {}
        rid = _row_get(row, "id")
        if rid is not None and str(rid).strip() != "":
            try:
                return GiftCard.objects.get(pk=int(rid))
            except (ValueError, TypeError, GiftCard.DoesNotExist):
                pass
        code = _row_get(row, "code", "Code")
        if code is None:
            return None
        return GiftCard.objects.filter(code=str(code).strip()[:64]).first()
