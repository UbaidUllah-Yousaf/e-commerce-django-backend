from rest_framework import serializers

from ecommerce.models.customer import CustomerAddress, CustomerProfile


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            "id",
            "first_name",
            "last_name",
            "company",
            "address1",
            "address2",
            "city",
            "province_code",
            "country_code",
            "zip",
            "phone",
            "is_default_shipping",
            "is_default_billing",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_country_code(self, value):
        v = (value or "").strip().upper()
        if len(v) != 2:
            raise serializers.ValidationError("country_code must be a 2-letter ISO code.")
        return v


class CustomerProfileSerializer(serializers.ModelSerializer):
    """Shopify-like customer: User identity + profile fields + nested addresses (read)."""

    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    addresses = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "note",
            "accepts_marketing",
            "tax_exempt",
            "addresses",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "addresses", "created_at", "updated_at")

    def get_addresses(self, obj):
        qs = obj.user.customer_addresses.order_by("id")
        return CustomerAddressSerializer(qs, many=True).data

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        instance = super().update(instance, validated_data)
        user = instance.user
        for key, val in user_data.items():
            setattr(user, key, val)
        user.save()
        return instance

