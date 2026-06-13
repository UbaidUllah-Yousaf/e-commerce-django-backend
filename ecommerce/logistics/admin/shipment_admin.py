from django.contrib import admin, messages
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from logistics.models.shipment import Shipment, ShipmentStatusHistory
from logistics.services.shipment_manager import ShipmentManager, ShipmentManagerError
from logistics.tasks.shipments import process_shipment_pipeline
from logistics.utils.status_display import admin_status_badge, shipment_status_view


class ShipmentStatusHistoryInline(TabularInline):
    model = ShipmentStatusHistory
    extra = 0
    readonly_fields = ("status", "source", "raw_payload", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Shipment)
class ShipmentAdmin(ModelAdmin):
    list_display = (
        "order_number",
        "external_order_id",
        "source_platform",
        "city",
        "courier_name",
        "fulfillment_status_badge",
        "delivery_status_badge",
        "tracking_summary",
        "ecommerce_order_link",
        "created_at",
    )
    list_filter = (
        "shipment_status",
        "processing_state",
        "source_platform",
        "courier_name",
        "city",
        "shop",
    )
    search_fields = (
        "order_number",
        "external_order_id",
        "tracking_number",
        "idempotency_key",
        "correlation_id",
    )
    readonly_fields = (
        "idempotency_key",
        "correlation_id",
        "fulfillment_status_badge",
        "delivery_status_badge",
        "status_summary_display",
        "request_payload",
        "response_payload",
        "last_celery_task_id",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Fulfillment",
            {
                "fields": (
                    "ecommerce_order",
                    "shop",
                    "source_platform",
                    "external_order_id",
                    "order_number",
                    "status_summary_display",
                    "fulfillment_status_badge",
                    "delivery_status_badge",
                    "processing_state",
                    "shipment_status",
                    "courier_name",
                    "service_type",
                    "tracking_number",
                    "tracking_url",
                    "quiqup_shipment_id",
                    "error_message",
                    "retry_count",
                ),
            },
        ),
        (
            "Payloads",
            {
                "classes": ("collapse",),
                "fields": (
                    "idempotency_key",
                    "correlation_id",
                    "request_payload",
                    "response_payload",
                    "last_celery_task_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    autocomplete_fields = ("shop", "ecommerce_order")
    inlines = [ShipmentStatusHistoryInline]
    actions = ["retry_shipment", "retry_quiqup_only"]

    @admin.display(description="Fulfillment")
    def fulfillment_status_badge(self, obj):
        view = shipment_status_view(obj)
        return admin_status_badge(view.processing_label, view.processing_tone)

    @admin.display(description="Delivery")
    def delivery_status_badge(self, obj):
        view = shipment_status_view(obj)
        return admin_status_badge(view.delivery_label, view.delivery_tone)

    @admin.display(description="Status")
    def status_summary_display(self, obj):
        view = shipment_status_view(obj)
        return format_html(
            "<strong>{}</strong><br><span style='color:#57534e;font-size:12px;'>{}</span>",
            view.headline,
            view.subline,
        )

    @admin.display(description="Tracking")
    def tracking_summary(self, obj):
        if not obj.tracking_number:
            return "—"
        if obj.tracking_url:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">{}</a>',
                obj.tracking_url,
                obj.tracking_number,
            )
        return obj.tracking_number

    @admin.display(description="Order")
    def ecommerce_order_link(self, obj):
        if not obj.ecommerce_order_id:
            return "—"
        return format_html(
            '<a href="/admin/ecommerce/order/{}/change/">{}</a>',
            obj.ecommerce_order_id,
            obj.ecommerce_order.name or obj.ecommerce_order_id,
        )

    @admin.action(description="Retry full pipeline")
    def retry_shipment(self, request, queryset):
        for shipment in queryset:
            process_shipment_pipeline.delay(
                shipment.pk,
                correlation_id=str(shipment.correlation_id),
            )
        self.message_user(
            request,
            f"Enqueued {queryset.count()} shipment(s) for full pipeline.",
            messages.SUCCESS,
        )

    @admin.action(description="Retry Quiqup step only")
    def retry_quiqup_only(self, request, queryset):
        for shipment in queryset:
            process_shipment_pipeline.delay(
                shipment.pk,
                correlation_id=str(shipment.correlation_id),
                steps=["quiqup"],
            )
        self.message_user(
            request,
            f"Enqueued {queryset.count()} shipment(s) for Quiqup retry.",
            messages.SUCCESS,
        )
