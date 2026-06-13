from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ecommerce.filters import (
    ProductFilter,
    ProductOptionFilter,
    ProductOptionValueFilter,
    ProductVariantFilter,
)
from ecommerce.models.product import ProductOptionValue, ProductOption, ProductVariant, Product
from ecommerce.serializers.product import ProductOptionValueSerializer, ProductOptionSerializer, \
    ProductVariantSerializer, ProductSerializer


class ProductOptionValueViewSet(viewsets.ModelViewSet):
    queryset = ProductOptionValue.objects.filter(
        option__product__deleted_at__isnull=True,
    )
    serializer_class = ProductOptionValueSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductOptionValueFilter
    ordering_fields = ("value", "created_at", "updated_at", "id")


# =========================================================
# PRODUCT OPTION VIEWSET
# =========================================================

class ProductOptionViewSet(viewsets.ModelViewSet):
    queryset = ProductOption.objects.filter(product__deleted_at__isnull=True)
    serializer_class = ProductOptionSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductOptionFilter
    ordering_fields = ("name", "created_at", "updated_at", "id")


# =========================================================
# PRODUCT VARIANT VIEWSET
# =========================================================

class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.filter(product__deleted_at__isnull=True)
    serializer_class = ProductVariantSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductVariantFilter
    ordering_fields = (
        "title",
        "sku",
        "price",
        "inventory_quantity",
        "created_at",
        "updated_at",
        "id",
    )


# =========================================================
# PRODUCT VIEWSET
# =========================================================

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all() \
        .prefetch_related(
            "variants",
            "tags",
            "options__values",
        ) \
        .select_related("collection")

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    ordering_fields = (
        "title",
        "handle",
        "status",
        "vendor",
        "product_type",
        "created_at",
        "updated_at",
        "id",
    )
