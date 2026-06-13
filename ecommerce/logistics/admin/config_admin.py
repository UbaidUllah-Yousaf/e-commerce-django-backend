from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.models.shipment import WebhookLog
from logistics.models.shopify import ShopifyConfiguration
from logistics.tasks.shipments import process_shopify_order_webhook


@admin.register(ShopifyConfiguration)
class ShopifyConfigurationAdmin(ModelAdmin):
    list_display = ("shop_name", "shop_domain", "api_version", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("shop_name", "shop_domain")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CityFulfillmentRule)
class CityFulfillmentRuleAdmin(ModelAdmin):
    list_display = ("city_name", "priority", "courier_name", "service_type", "is_active")
    list_editable = ("is_active",)
    list_filter = ("is_active", "courier_name")
    ordering = ("priority", "city_name")


@admin.register(CourierConfiguration)
class CourierConfigurationAdmin(ModelAdmin):
    list_display = ("courier_name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("courier_name",)


@admin.register(FulfillmentConfiguration)
class FulfillmentConfigurationAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return not FulfillmentConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookLog)
class WebhookLogAdmin(ModelAdmin):
    list_display = (
        "id",
        "source_platform",
        "event_type",
        "shop",
        "processed",
        "correlation_id",
        "created_at",
    )
    list_filter = ("processed", "source_platform", "shop")
    readonly_fields = (
        "shop",
        "source_platform",
        "event_type",
        "payload",
        "processed",
        "error_message",
        "correlation_id",
        "created_at",
        "updated_at",
    )
    actions = ["reprocess_webhook"]

    @admin.action(description="Reprocess selected webhooks")
    def reprocess_webhook(self, request, queryset):
        count = 0
        for log in queryset:
            process_shopify_order_webhook.delay(log.pk, correlation_id=str(log.correlation_id))
            count += 1
        self.message_user(request, f"Enqueued {count} webhook(s).", messages.SUCCESS)
