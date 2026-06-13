from rest_framework import serializers

from ecommerce.models.gift_card import GiftCard
from ecommerce.validators import MIN_IDENTIFIER_LENGTH


class GiftCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftCard
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
        read_only_fields = ("current_balance", "created_at", "updated_at")

    def validate_code(self, value):
        v = value.strip().upper()
        if len(v) < MIN_IDENTIFIER_LENGTH:
            raise serializers.ValidationError(
                f"Identifier must be at least {MIN_IDENTIFIER_LENGTH} characters."
            )
        return v

    def create(self, validated_data):
        initial = validated_data["initial_balance"]
        validated_data.setdefault("current_balance", initial)
        return super().create(validated_data)
