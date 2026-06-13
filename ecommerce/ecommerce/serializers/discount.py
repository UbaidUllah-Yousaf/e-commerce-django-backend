from decimal import Decimal

from rest_framework import serializers

from ecommerce.constants.discount import (
    DISCOUNT_TYPE_FIXED_AMOUNT,
    DISCOUNT_TYPE_PERCENTAGE,
)
from ecommerce.models.discount import DiscountCode
from ecommerce.validators import MIN_IDENTIFIER_LENGTH


class DiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
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
        read_only_fields = ("usage_count", "created_at", "updated_at")

    def validate_code(self, value):
        v = value.strip().upper()
        if len(v) < MIN_IDENTIFIER_LENGTH:
            raise serializers.ValidationError(
                f"Identifier must be at least {MIN_IDENTIFIER_LENGTH} characters."
            )
        return v

    def validate(self, attrs):
        discount_type = attrs.get("discount_type")
        if self.instance:
            discount_type = discount_type or self.instance.discount_type
        value = attrs.get("value")
        if value is not None and discount_type == DISCOUNT_TYPE_PERCENTAGE:
            if value < Decimal("0") or value > Decimal("100"):
                raise serializers.ValidationError(
                    {"value": "Percentage must be between 0 and 100."}
                )
        if value is not None and discount_type == DISCOUNT_TYPE_FIXED_AMOUNT and value < Decimal("0"):
            raise serializers.ValidationError({"value": "Fixed amount cannot be negative."})
        return attrs
