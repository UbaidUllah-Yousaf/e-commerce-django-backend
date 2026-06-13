from rest_framework import serializers

from ecommerce.constants.fulfillment import (
    FULFILLMENT_CREATE_SCOPE_CHOICES,
    FULFILLMENT_CREATE_SCOPE_COMPLETE,
    FULFILLMENT_CREATE_SCOPE_PARTIAL,
    SHIPMENT_STATUS_CHOICES,
    SHIPMENT_STATUS_LABELS,
    SHIPMENT_STATUS_SUCCESS,
)
from ecommerce.models.fulfillment import Fulfillment, FulfillmentLineItem, FulfillmentService


class CreateOrderFulfillmentLineSerializer(serializers.Serializer):
    order_line_item = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderFulfillmentSerializer(serializers.Serializer):
    """
    Shopify Admin API–style create fulfillment.

    * scope ``complete`` — all remaining units on the order.
    * scope ``partial`` — explicit ``line_items`` [{order_line_item, quantity}, ...].
    * manual — manual fulfillment (no fulfillment_service).
    """

    scope = serializers.ChoiceField(choices=FULFILLMENT_CREATE_SCOPE_CHOICES)
    manual = serializers.BooleanField(default=False)
    fulfillment_service = serializers.PrimaryKeyRelatedField(
        queryset=FulfillmentService.objects.all(),
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        default="",
    )
    notify_customer = serializers.BooleanField(default=False)
    tracking_company = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        default="",
    )
    tracking_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        default="",
    )
    tracking_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )
    status = serializers.ChoiceField(
        choices=SHIPMENT_STATUS_CHOICES,
        default=SHIPMENT_STATUS_SUCCESS,
    )
    line_items = CreateOrderFulfillmentLineSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs["scope"] == FULFILLMENT_CREATE_SCOPE_PARTIAL and not attrs.get("line_items"):
            raise serializers.ValidationError(
                {"line_items": "Required when scope is partial."}
            )
        if attrs["scope"] == FULFILLMENT_CREATE_SCOPE_COMPLETE and attrs.get("line_items"):
            raise serializers.ValidationError(
                {
                    "line_items": (
                        "Omit line_items when scope is complete. "
                        "Use scope partial for explicit lines."
                    )
                }
            )
        svc = attrs.get("fulfillment_service")
        if svc and not svc.is_active:
            raise serializers.ValidationError(
                {"fulfillment_service": "This fulfillment service is not active."}
            )
        return attrs


class FulfillmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FulfillmentService
        fields = (
            "id",
            "name",
            "courier_name",
            "carrier_code",
            "tracking_url_template",
            "is_active",
            "notes",
            "logo",
            "created_at",
            "updated_at",
        )


class FulfillmentLineItemSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="order_line_item.product_title", read_only=True)
    variant_title = serializers.CharField(source="order_line_item.variant_title", read_only=True)
    sku = serializers.CharField(source="order_line_item.sku", read_only=True)

    class Meta:
        model = FulfillmentLineItem
        fields = (
            "id",
            "order_line_item",
            "product_title",
            "variant_title",
            "sku",
            "quantity",
            "created_at",
            "updated_at",
        )


class FulfillmentSerializer(serializers.ModelSerializer):
    """Shopify-style fulfillment on order reads (one package / wave)."""

    fulfillment_service_detail = FulfillmentServiceSerializer(
        source="fulfillment_service",
        read_only=True,
    )
    line_items = FulfillmentLineItemSerializer(many=True, read_only=True)
    status_label = serializers.SerializerMethodField()
    tracking_company = serializers.SerializerMethodField()
    tracking_url = serializers.SerializerMethodField()

    class Meta:
        model = Fulfillment
        fields = (
            "id",
            "order",
            "fulfillment_service",
            "fulfillment_service_detail",
            "name",
            "status",
            "status_label",
            "tracking_company",
            "tracking_number",
            "tracking_url",
            "notify_customer",
            "shipped_at",
            "delivered_at",
            "line_items",
            "created_at",
            "updated_at",
        )

    def get_status_label(self, obj):
        return SHIPMENT_STATUS_LABELS.get(obj.status, obj.status)

    def get_tracking_company(self, obj):
        return obj.effective_tracking_company()

    def get_tracking_url(self, obj):
        return obj.effective_tracking_url()
