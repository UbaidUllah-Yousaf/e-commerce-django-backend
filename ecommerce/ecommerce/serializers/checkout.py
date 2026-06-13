from decimal import Decimal

from rest_framework import serializers

from ecommerce.constants.checkout import CHECKOUT_STATUS_OPEN, ORDER_FINANCIAL_CHOICES
from ecommerce.constants.fulfillment import FULFILLMENT_STATUS_CHOICES
from ecommerce.models.checkout import (
    Checkout,
    CheckoutGiftCardApplication,
    CheckoutLineItem,
    Order,
    OrderLineItem,
)
from ecommerce.serializers.product import ProductVariantSerializer
from ecommerce.validators import MIN_IDENTIFIER_LENGTH
from ecommerce.serializers.fulfillment import FulfillmentSerializer
from ecommerce.services import checkout_pricing
from ecommerce.services.checkout_payment_settings import (
    cod_complete_allowed,
    get_stripe_status,
    payment_required_for_checkout,
    stripe_checkout_available,
)

_FULFILLMENT_STATUS_LABELS = dict(FULFILLMENT_STATUS_CHOICES)
_FINANCIAL_STATUS_LABELS = dict(ORDER_FINANCIAL_CHOICES)


class CheckoutLineItemSerializer(serializers.ModelSerializer):
    variant_detail = ProductVariantSerializer(source="variant", read_only=True)

    class Meta:
        model = CheckoutLineItem
        fields = (
            "id",
            "checkout",
            "variant",
            "variant_detail",
            "quantity",
            "unit_price",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unit_price", "created_at", "updated_at")

    def validate(self, attrs):
        variant = attrs.get("variant") or getattr(self.instance, "variant", None)
        if variant and not variant.is_active:
            raise serializers.ValidationError({"variant": "This variant is not available."})
        if variant and variant.product.status != "active":
            raise serializers.ValidationError({"variant": "This product is not active."})
        if variant and not variant.product.is_published:
            raise serializers.ValidationError({"variant": "This product is not published."})
        return attrs

    def create(self, validated_data):
        checkout = validated_data["checkout"]
        variant = validated_data["variant"]
        quantity = int(validated_data.get("quantity") or 1)
        if quantity < 1:
            raise serializers.ValidationError({"quantity": "Must be at least 1."})

        existing = CheckoutLineItem.objects.filter(
            checkout=checkout,
            variant=variant,
        ).first()
        if existing:
            existing.quantity += quantity
            existing.unit_price = variant.price
            existing.save()
            checkout_pricing.recalculate_checkout(checkout)
            return existing

        validated_data["quantity"] = quantity
        validated_data["unit_price"] = variant.price
        li = super().create(validated_data)
        checkout_pricing.recalculate_checkout(checkout)
        return li

    def update(self, instance, validated_data):
        checkout = instance.checkout
        if "variant" in validated_data and validated_data["variant"] != instance.variant:
            raise serializers.ValidationError({"variant": "Cannot change variant; remove and add a line."})
        instance = super().update(instance, validated_data)
        checkout_pricing.recalculate_checkout(checkout)
        return instance


class CheckoutGiftCardApplicationSerializer(serializers.ModelSerializer):
    gift_card_code = serializers.CharField(source="gift_card.code", read_only=True)

    class Meta:
        model = CheckoutGiftCardApplication
        fields = (
            "id",
            "checkout",
            "gift_card",
            "gift_card_code",
            "amount_applied",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("amount_applied", "created_at", "updated_at")


class CheckoutSerializer(serializers.ModelSerializer):
    line_items = CheckoutLineItemSerializer(many=True, read_only=True)
    gift_card_applications = CheckoutGiftCardApplicationSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()
    discount_code_string = serializers.CharField(source="discount_code.code", read_only=True)
    payment_required = serializers.SerializerMethodField()
    stripe_enabled = serializers.SerializerMethodField()
    cod_allowed = serializers.SerializerMethodField()
    stripe_status = serializers.SerializerMethodField()

    class Meta:
        model = Checkout
        fields = (
            "id",
            "token",
            "email",
            "phone",
            "currency",
            "status",
            "note",
            "shipping_address",
            "billing_address",
            "billing_same_as_shipping",
            "shipping_total",
            "tax_total",
            "discount_code",
            "discount_code_string",
            "discount_amount",
            "line_items",
            "gift_card_applications",
            "totals",
            "payment_required",
            "stripe_enabled",
            "cod_allowed",
            "stripe_status",
            "stripe_checkout_session_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "token",
            "status",
            "discount_amount",
            "discount_code",
            "stripe_checkout_session_id",
            "created_at",
            "updated_at",
        )

    def get_payment_required(self, obj):
        if obj.status != CHECKOUT_STATUS_OPEN:
            return False
        return payment_required_for_checkout(checkout_pricing.checkout_totals(obj)["total"])

    def get_stripe_enabled(self, obj):
        return stripe_checkout_available()

    def get_cod_allowed(self, obj):
        return cod_complete_allowed()

    def get_stripe_status(self, obj):
        return get_stripe_status()

    def get_totals(self, obj):
        return checkout_pricing.checkout_totals(obj)

    def validate_shipping_total(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("Shipping cannot be negative.")
        return value

    def validate_tax_total(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("Tax cannot be negative.")
        return value

    def update(self, instance, validated_data):
        if instance.status != CHECKOUT_STATUS_OPEN:
            raise serializers.ValidationError("Only open checkouts can be updated.")
        checkout = super().update(instance, validated_data)
        checkout_pricing.recalculate_checkout(checkout)
        return checkout


class OrderLineItemSerializer(serializers.ModelSerializer):
    fulfillment_status_label = serializers.SerializerMethodField()
    variant_detail = ProductVariantSerializer(source="variant", read_only=True)

    class Meta:
        model = OrderLineItem
        fields = (
            "id",
            "variant",
            "variant_detail",
            "product_title",
            "variant_title",
            "sku",
            "quantity",
            "unit_price",
            "line_total",
            "fulfillment_status",
            "fulfillment_status_label",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "fulfillment_status",
            "fulfillment_status_label",
            "created_at",
            "updated_at",
        )

    def get_fulfillment_status_label(self, obj):
        return _FULFILLMENT_STATUS_LABELS.get(obj.fulfillment_status, obj.fulfillment_status)


class OrderSerializer(serializers.ModelSerializer):
    line_items = OrderLineItemSerializer(many=True, read_only=True)
    fulfillments = FulfillmentSerializer(many=True, read_only=True)
    fulfillment_status_label = serializers.SerializerMethodField()
    financial_status_label = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "name",
            "order_number",
            "checkout",
            "token",
            "email",
            "phone",
            "currency",
            "shipping_address",
            "billing_address",
            "subtotal",
            "discount_amount",
            "shipping_total",
            "tax_total",
            "gift_card_total",
            "total",
            "discount_code_snapshot",
            "financial_status",
            "financial_status_label",
            "stripe_payment_intent_id",
            "fulfillment_status",
            "fulfillment_status_label",
            "note",
            "line_items",
            "fulfillments",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "name",
            "order_number",
            "checkout",
            "token",
            "email",
            "phone",
            "currency",
            "shipping_address",
            "billing_address",
            "subtotal",
            "discount_amount",
            "shipping_total",
            "tax_total",
            "gift_card_total",
            "total",
            "discount_code_snapshot",
            "financial_status",
            "financial_status_label",
            "stripe_payment_intent_id",
            "fulfillment_status",
            "fulfillment_status_label",
            "note",
            "line_items",
            "fulfillments",
            "created_at",
            "updated_at",
        )

    def get_fulfillment_status_label(self, obj):
        return _FULFILLMENT_STATUS_LABELS.get(obj.fulfillment_status, obj.fulfillment_status)

    def get_financial_status_label(self, obj):
        return _FINANCIAL_STATUS_LABELS.get(obj.financial_status, obj.financial_status)


class ApplyDiscountSerializer(serializers.Serializer):
    """
    Accept the canonical ``code`` or common storefront aliases ``coupon_code`` / ``discount_code``.
    Only one non-empty value is required; checked length is after strip.
    """

    code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    coupon_code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    discount_code = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, attrs):
        raw = ""
        for key in ("code", "coupon_code", "discount_code"):
            val = attrs.get(key)
            if val is None:
                continue
            s = str(val).strip()
            if s:
                raw = s
                break
        if len(raw) < MIN_IDENTIFIER_LENGTH:
            raise serializers.ValidationError(
                {
                    "code": (
                        f"Provide `code`, `coupon_code`, or `discount_code` "
                        f"(at least {MIN_IDENTIFIER_LENGTH} characters after trimming)."
                    )
                }
            )
        attrs["code"] = raw
        return attrs


class ApplyGiftCardSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64, min_length=MIN_IDENTIFIER_LENGTH)


class RemoveGiftCardSerializer(serializers.Serializer):
    gift_card_id = serializers.IntegerField(required=False)
    code = serializers.CharField(max_length=64, required=False)

    def validate(self, attrs):
        if not attrs.get("gift_card_id") and not attrs.get("code"):
            raise serializers.ValidationError("Provide gift_card_id or code.")
        raw = attrs.get("code")
        if raw is not None and len(str(raw).strip()) < MIN_IDENTIFIER_LENGTH:
            raise serializers.ValidationError(
                {
                    "code": (
                        f"When using code, it must be at least {MIN_IDENTIFIER_LENGTH} characters."
                    )
                }
            )
        return attrs
