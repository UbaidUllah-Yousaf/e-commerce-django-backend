from rest_framework import serializers

from ecommerce.models.product import ProductOptionValue, ProductOption, ProductVariant, Product
from ecommerce.serializers.collection import CollectionSerializer
from ecommerce.serializers.tag import TagSerializer


# =========================================================
# PRODUCT OPTION VALUE
# =========================================================

class ProductOptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOptionValue
        fields = "__all__"


# =========================================================
# PRODUCT OPTION
# =========================================================

class ProductOptionSerializer(serializers.ModelSerializer):
    values = ProductOptionValueSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = ProductOption
        fields = "__all__"


# =========================================================
# PRODUCT VARIANT
# =========================================================

class ProductVariantSerializer(serializers.ModelSerializer):
    option_values = ProductOptionValueSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = "__all__"


# =========================================================
# PRODUCT
# =========================================================

class ProductSerializer(serializers.ModelSerializer):
    collection = CollectionSerializer(read_only=True)

    tags = TagSerializer(
        many=True,
        read_only=True
    )

    variants = ProductVariantSerializer(
        many=True,
        read_only=True
    )

    options = ProductOptionSerializer(
        many=True,
        read_only=True
    )

    min_price = serializers.ReadOnlyField()
    max_price = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = "__all__"
