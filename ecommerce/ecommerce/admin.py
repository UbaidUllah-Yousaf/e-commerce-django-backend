import json
from decimal import Decimal

from django.contrib import admin
from django.db.models import Min, Max
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm

from ecommerce.import_export_resources import (
    CollectionResource,
    DiscountCodeResource,
    GiftCardResource,
    ProductResource,
    ProductVariantResource,
    TagResource,
)

from ecommerce.models.checkout import (
    Checkout,
    CheckoutGiftCardApplication,
    CheckoutLineItem,
    Order,
    OrderLineItem,
)
from ecommerce.models.checkout_payment import CheckoutPaymentSettings
from ecommerce.services import checkout_pricing
from ecommerce.services.checkout_payment_settings import (
    build_checkout_redirect_urls,
    get_checkout_payment_settings,
)
from ecommerce.models.collection import Collection
from ecommerce.models.customer import CustomerAddress, CustomerProfile
from ecommerce.models.discount import DiscountCode
from ecommerce.models.fulfillment import (
    Fulfillment,
    FulfillmentLineItem,
    FulfillmentService,
)
from ecommerce.models.gift_card import GiftCard
from ecommerce.forms.size_chart_admin import SizeChartAdminForm
from ecommerce.models.product import ProductOptionValue, ProductOption, ProductVariant, Product
from ecommerce.models.size_chart import (
    SizeChart,
    SizeChartCell,
    SizeChartColumn,
    SizeChartRow,
)
from ecommerce.models.tag import Tag
from ecommerce.services.size_chart_grid import apply_grid_payload_to_chart
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from django.utils.html import format_html


class DeletionStateFilter(admin.SimpleListFilter):
    title = "Deletion state"
    parameter_name = "deletion"

    def lookups(self, request, model_admin):
        return (
            ("active", "Not deleted"),
            ("deleted", "Soft-deleted"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == "deleted":
            return queryset.filter(deleted_at__isnull=False)
        if v == "all":
            return queryset
        return queryset.filter(deleted_at__isnull=True)


class UnfoldImportExportAdmin(ModelAdmin, ImportExportModelAdmin):
    """Combines Unfold styling with django-import-export (CSV, XLSX, …)."""

    import_form_class = ImportForm
    export_form_class = ExportForm


# =========================================================
# TAG ADMIN
# =========================================================


class SizeChartInline(StackedInline):
    model = SizeChart
    extra = 0
    max_num = 1
    fields = ("title", "is_active")
    verbose_name = "Size chart (summary)"
    verbose_name_plural = "Size chart (summary)"


@admin.register(Tag)
class TagAdmin(UnfoldImportExportAdmin):
    resource_classes = [TagResource]
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [SizeChartInline]


# =========================================================
# SIZE CHART ADMIN
# =========================================================


@admin.register(SizeChart)
class SizeChartAdmin(ModelAdmin):
    form = SizeChartAdminForm
    change_form_template = "admin/ecommerce/sizechart/change_form.html"
    list_display = ("tag", "title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("tag__name", "title")
    autocomplete_fields = ("tag",)
    fieldsets = (
        (
            None,
            {
                "fields": ("tag", "title", "is_active", "grid_data"),
                "description": "Use the measurement grid below for rows, columns, and values.",
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if isinstance(form, SizeChartAdminForm):
            raw = form.cleaned_data.get("grid_data")
            if raw:
                apply_grid_payload_to_chart(obj, json.loads(raw))


@admin.register(SizeChartRow)
class SizeChartRowAdmin(ModelAdmin):
    list_display = ("label", "sort_order", "chart")
    list_filter = ("chart",)
    search_fields = ("label", "chart__tag__name")
    autocomplete_fields = ("chart",)


@admin.register(SizeChartColumn)
class SizeChartColumnAdmin(ModelAdmin):
    list_display = ("label", "sort_order", "chart")
    list_filter = ("chart",)
    search_fields = ("label", "chart__tag__name")
    autocomplete_fields = ("chart",)


# =========================================================
# COLLECTION ADMIN
# =========================================================

@admin.register(Collection)
class CollectionAdmin(UnfoldImportExportAdmin):
    resource_classes = [CollectionResource]
    list_display = (
        "image_preview",
        "title",
        "products_count",
        "is_active",
        "deleted_at",
        "created_at",
    )

    list_filter = ("is_active", DeletionStateFilter)

    search_fields = ("title",)

    def get_queryset(self, request):
        return Collection.all_objects.all().order_by("title")

    prepopulated_fields = {"handle": ("title",)}

    readonly_fields = ("deleted_at", "created_at", "updated_at")

    fieldsets = (
        (
            "Collection Information",
            {
                "fields": (
                    "title",
                    "handle",
                    "description",
                    "image",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "deleted_at",
                )
            },
        ),
    )

    actions = ("soft_delete_collections", "restore_collections")

    @admin.action(description="Soft-delete selected collections")
    def soft_delete_collections(self, request, queryset):
        queryset.delete()

    @admin.action(description="Restore soft-deleted collections")
    def restore_collections(self, request, queryset):
        queryset.filter(deleted_at__isnull=False).restore()

    def products_count(self, obj):
        return obj.product_set.count()

    products_count.short_description = "Products"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 6px;" />',
                obj.image.url
            )
        return "-"

    image_preview.short_description = "Image"


# =========================================================
# INLINE CONFIGURATIONS
# =========================================================

class ProductOptionValueInline(TabularInline):
    model = ProductOptionValue
    extra = 1


class ProductOptionInline(StackedInline):
    model = ProductOption
    extra = 1
    show_change_link = True


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    readonly_fields = ("image_preview",)
    fields = (
        "image_preview",
        "title",
        "sku",
        "barcode",
        "price",
        "inventory_quantity",
        "is_active",
    )

    def image_preview(self, obj):
        if getattr(obj, "image", None) and obj.image:
            return format_html(
                '<img src="{}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 6px;" />',
                obj.image.url
            )
        return "-"

    image_preview.short_description = "Image"


# =========================================================
# PRODUCT OPTION ADMIN
# =========================================================

@admin.register(ProductOption)
class ProductOptionAdmin(ModelAdmin):
    list_display = ("name", "product")
    search_fields = ("name", "product__title")
    inlines = [ProductOptionValueInline]


# =========================================================
# PRODUCT VARIANT ADMIN
# =========================================================

@admin.register(ProductVariant)
class ProductVariantAdmin(UnfoldImportExportAdmin):
    resource_classes = [ProductVariantResource]
    list_display = (
        "image_preview",
        "title",
        "product",
        "sku",
        "price",
        "inventory_quantity",
        "is_active",
    )

    list_filter = (
        "is_active",
        "product",
    )

    search_fields = (
        "title",
        "sku",
        "product__title",
    )

    filter_horizontal = ("option_values",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "product",
                    "title",
                    "sku",
                    "barcode",
                    "image",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price",
                    "compare_at_price",
                    "cost_per_item",
                )
            },
        ),
        (
            "Inventory",
            {
                "fields": (
                    "inventory_quantity",
                    "weight",
                    "is_active",
                )
            },
        ),
        (
            "Variant Options",
            {
                "fields": (
                    "option_values",
                )
            },
        ),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 6px;" />',
                obj.image.url
            )
        return "-"

    image_preview.short_description = "Image"


# =========================================================
# PRODUCT ADMIN
# =========================================================

@admin.register(Product)
class ProductAdmin(UnfoldImportExportAdmin):
    resource_classes = [ProductResource]
    list_display = (
        "image_preview",
        "title",
        "collection",
        "status",
        "price_range",
        "total_inventory",
        "variants_count",
        "is_published",
        "deleted_at",
        "created_at",
    )

    list_filter = (
        DeletionStateFilter,
        "status",
        "is_published",
        "gift_card",
        "published_scope",
        "collection",
        "tags",
    )

    search_fields = (
        "title",
        "description",
        "body_html",
        "vendor",
        "product_type",
        "product_category",
        "seo_title",
    )

    prepopulated_fields = {"handle": ("title",)}

    autocomplete_fields = ("collection",)

    filter_horizontal = ("tags",)

    inlines = [
        ProductOptionInline,
        ProductVariantInline,
    ]

    readonly_fields = (
        "deleted_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Product Information",
            {
                "fields": (
                    "title",
                    "handle",
                    "body_html",
                    "description",
                    "featured_image",
                )
            },
        ),
        (
            "Organization",
            {
                "fields": (
                    "collection",
                    "tags",
                    "vendor",
                    "product_type",
                    "product_category",
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "seo_title",
                    "seo_description",
                )
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "status",
                    "is_published",
                    "published_scope",
                    "published_at",
                    "template_suffix",
                    "gift_card",
                )
            },
        ),
        (
            "Soft delete",
            {
                "fields": ("deleted_at",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = [
        "publish_products",
        "unpublish_products",
        "soft_delete_products",
        "restore_products",
    ]

    def get_queryset(self, request):
        return (
            Product.all_objects.all()
            .select_related("collection")
            .prefetch_related("variants", "tags", "options__values")
        )

    def variants_count(self, obj):
        return obj.variants.count()

    variants_count.short_description = "Variants"

    def total_inventory(self, obj):
        return sum(v.inventory_quantity for v in obj.variants.all())

    total_inventory.short_description = "Inventory"

    def price_range(self, obj):
        prices = obj.variants.aggregate(
            min_price=Min("price"),
            max_price=Max("price")
        )

        min_price = prices["min_price"]
        max_price = prices["max_price"]

        if min_price is None:
            return "-"

        if min_price == max_price:
            return f"${min_price}"

        return f"${min_price} - ${max_price}"

    price_range.short_description = "Price"

    # -----------------------------------------------------
    # BULK ACTIONS
    # -----------------------------------------------------

    @admin.action(description="Publish selected products")
    def publish_products(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Unpublish selected products")
    def unpublish_products(self, request, queryset):
        queryset.update(is_published=False)

    @admin.action(description="Soft-delete selected products")
    def soft_delete_products(self, request, queryset):
        queryset.delete()

    @admin.action(description="Restore soft-deleted products")
    def restore_products(self, request, queryset):
        queryset.filter(deleted_at__isnull=False).restore()

    def image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 6px;" />',
                obj.featured_image.url
            )
        return "-"

    image_preview.short_description = "Image"


class CheckoutLineItemInline(TabularInline):
    model = CheckoutLineItem
    extra = 0
    autocomplete_fields = ("variant",)


class CheckoutGiftCardInline(TabularInline):
    model = CheckoutGiftCardApplication
    extra = 0
    autocomplete_fields = ("gift_card",)
    readonly_fields = ("amount_applied",)


@admin.register(CheckoutPaymentSettings)
class CheckoutPaymentSettingsAdmin(ModelAdmin):
    """Singleton: configure how checkout accepts payment (Stripe vs COD)."""

    fieldsets = (
        (
            "Stripe Checkout",
            {
                "fields": ("stripe_checkout_enabled", "stripe_status_display"),
                "description": (
                    "Turning Stripe on here only activates it when "
                    "STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY are set in "
                    "ecommerce/.env (see .env.example). STRIPE_WEBHOOK_SECRET is "
                    "required for webhooks."
                ),
            },
        ),
        (
            "Cash on delivery (COD)",
            {
                "fields": ("allow_cod_complete",),
                "description": (
                    "When enabled, customers can place paid orders via "
                    "POST /checkouts/{id}/complete/ without Stripe. Orders use "
                    "financial_status pending until staff marks them paid."
                ),
            },
        ),
        (
            "Default redirect URLs (React + Vite)",
            {
                "fields": (
                    "generated_urls_preview",
                    "default_success_url",
                    "default_cancel_url",
                ),
                "description": (
                    "Leave blank to use URLs generated from STOREFRONT_BASE_URL in .env "
                    "(default http://localhost:5173). success_url must contain "
                    "{CHECKOUT_SESSION_ID}. Use the admin action to reset from env."
                ),
            },
        ),
        (
            "Notes",
            {"fields": ("checkout_payment_note",), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ("generated_urls_preview", "stripe_status_display")
    actions = ("apply_generated_vite_urls",)

    def has_add_permission(self, request):
        return not CheckoutPaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Stripe operational status")
    def stripe_status_display(self, obj):
        from ecommerce.services.checkout_payment_settings import get_stripe_status

        status = get_stripe_status()
        if status["stripe_checkout_available"]:
            return format_html('<span style="color:green;">Available</span> (admin on, API keys set)')
        reason = status["unavailable_reason"] or "Not available"
        return format_html(
            '<span style="color:#b45309;">Not available</span><br><small>{}</small>',
            reason,
        )

    @admin.display(description="Generated from STOREFRONT_BASE_URL (.env)")
    def generated_urls_preview(self, obj):
        urls = build_checkout_redirect_urls()
        return format_html(
            "<strong>Success</strong><br><code>{}</code><br><br>"
            "<strong>Cancel</strong><br><code>{}</code>",
            urls["success_url"],
            urls["cancel_url"],
        )

    @admin.action(description="Reset redirect URLs from STOREFRONT_BASE_URL (.env)")
    def apply_generated_vite_urls(self, request, queryset):
        urls = build_checkout_redirect_urls()
        updated = queryset.update(
            default_success_url=urls["success_url"],
            default_cancel_url=urls["cancel_url"],
        )
        self.message_user(request, f"Updated redirect URLs on {updated} row(s).")

    def changelist_view(self, request, extra_context=None):
        get_checkout_payment_settings()
        return super().changelist_view(request, extra_context=extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        get_checkout_payment_settings()
        if object_id is None:
            object_id = "1"
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(Checkout)
class CheckoutAdmin(ModelAdmin):
    list_display = (
        "id",
        "token",
        "status",
        "email",
        "currency",
        "stripe_checkout_session_id",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = ("email", "token", "stripe_checkout_session_id")
    readonly_fields = (
        "token",
        "discount_amount",
        "stripe_checkout_session_id",
        "payment_summary",
        "created_at",
        "updated_at",
    )
    inlines = [CheckoutLineItemInline, CheckoutGiftCardInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "status",
                    "email",
                    "phone",
                    "currency",
                    "note",
                ),
            },
        ),
        (
            "Addresses & totals",
            {
                "fields": (
                    "shipping_address",
                    "billing_address",
                    "billing_same_as_shipping",
                    "shipping_total",
                    "tax_total",
                    "discount_code",
                    "discount_amount",
                ),
            },
        ),
        (
            "Payment",
            {
                "fields": ("stripe_checkout_session_id", "payment_summary"),
                "description": (
                    "Storefront payment options are configured under "
                    "Checkout payment settings. Staff can complete open checkouts "
                    "from the admin when COD is enabled in payment settings."
                ),
            },
        ),
    )
    actions = ("admin_complete_checkout",)

    @admin.display(description="Payment")
    def payment_summary(self, obj):
        if obj.pk is None:
            return "—"
        totals = checkout_pricing.checkout_totals(obj)
        opts = get_checkout_payment_settings()
        lines = [
            f"Total due: {totals['total']} {obj.currency}",
            f"Stripe (admin): {'on' if opts.stripe_checkout_enabled else 'off'}",
            f"COD: {'allowed' if opts.allow_cod_complete else 'blocked'}",
        ]
        if obj.stripe_checkout_session_id:
            lines.append(f"Session: {obj.stripe_checkout_session_id}")
        return format_html("<br>".join(lines))

    @admin.action(description="Complete checkout (COD / zero-total)")
    def admin_complete_checkout(self, request, queryset):
        from ecommerce.constants.checkout import ORDER_FINANCIAL_PAID, ORDER_FINANCIAL_PENDING
        from ecommerce.services.checkout_pricing import complete_checkout

        opts = get_checkout_payment_settings()
        completed = 0
        errors = []
        for checkout in queryset.filter(status="open"):
            due = Decimal(checkout_pricing.checkout_totals(checkout)["total"])
            if due > Decimal("0.00") and not opts.allow_cod_complete:
                errors.append(
                    f"Checkout {checkout.pk}: enable Cash on delivery in payment settings."
                )
                continue
            financial_status = ORDER_FINANCIAL_PAID
            if due > Decimal("0.00") and opts.allow_cod_complete:
                financial_status = ORDER_FINANCIAL_PENDING
            try:
                complete_checkout(checkout, financial_status=financial_status)
                completed += 1
            except ValueError as exc:
                errors.append(f"Checkout {checkout.pk}: {exc}")
        if completed:
            self.message_user(request, f"Completed {completed} checkout(s).")
        for err in errors:
            self.message_user(request, err, level="ERROR")


class OrderLineItemInline(TabularInline):
    model = OrderLineItem
    extra = 0
    autocomplete_fields = ("variant",)
    fields = (
        "variant",
        "product_title",
        "variant_title",
        "sku",
        "quantity",
        "unit_price",
        "line_total",
        "fulfillment_status",
    )
    readonly_fields = (
        "product_title",
        "variant_title",
        "sku",
    )


class FulfillmentInline(TabularInline):
    model = Fulfillment
    extra = 0
    show_change_link = True
    fields = (
        "fulfillment_service",
        "status",
        "logistics_shipment",
        "tracking_company",
        "tracking_number",
        "tracking_url",
        "name",
        "notify_customer",
        "shipped_at",
        "delivered_at",
    )
    autocomplete_fields = ("fulfillment_service",)


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        "id",
        "name",
        "order_number",
        "token",
        "total",
        "financial_status",
        "fulfillment_status",
        "currency",
        "created_at",
    )
    list_filter = ("financial_status", "currency", "fulfillment_status")
    search_fields = ("token", "email", "id", "name", "order_number", "customer__email", "customer__username")
    readonly_fields = (
        "checkout",
        "token",
        "order_number",
        "name",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Fulfillment",
            {
                "description": (
                    "Stored on the order row. Staff can set this manually; "
                    "saving or deleting related fulfillments recomputes it from "
                    "fulfillment quantities and tracking."
                ),
                "fields": ("fulfillment_status",),
            },
        ),
        (
            "Order",
            {
                "fields": (
                    "checkout",
                    "customer",
                    "token",
                    "name",
                    "order_number",
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
                    "note",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    inlines = [OrderLineItemInline, FulfillmentInline]


class FulfillmentLineItemInline(TabularInline):
    model = FulfillmentLineItem
    extra = 0
    fields = ("order_line_item", "quantity")
    autocomplete_fields = ("order_line_item",)

    def get_formset(self, request, obj=None, **kwargs):
        FormSet = super().get_formset(request, obj, **kwargs)
        order_id = obj.order_id if obj else None

        class FilteredFormSet(FormSet):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if order_id is None:
                    return
                for form in self.forms:
                    fld = form.fields.get("order_line_item")
                    if fld is not None:
                        fld.queryset = OrderLineItem.objects.filter(order_id=order_id)

        return FilteredFormSet


@admin.register(FulfillmentService)
class FulfillmentServiceAdmin(ModelAdmin):
    list_display = (
        "logo_preview",
        "courier_name",
        "name",
        "carrier_code",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "courier_name", "carrier_code")

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 6px;" />',
                obj.logo.url
            )
        return "-"

    logo_preview.short_description = "Logo"


@admin.register(Fulfillment)
class FulfillmentAdmin(ModelAdmin):
    list_display = (
        "id",
        "order",
        "fulfillment_service",
        "status",
        "tracking_number",
        "effective_carrier",
        "shipped_at",
        "created_at",
    )
    list_filter = ("status", "fulfillment_service")
    search_fields = ("tracking_number", "name", "order__token", "order__email", "order__name")
    autocomplete_fields = ("order", "fulfillment_service")
    readonly_fields = ("effective_carrier", "effective_tracking_url_display")
    inlines = [FulfillmentLineItemInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "order",
                    "fulfillment_service",
                    "name",
                    "status",
                )
            },
        ),
        (
            "Tracking",
            {
                "fields": (
                    "tracking_company",
                    "tracking_number",
                    "tracking_url",
                    "effective_carrier",
                    "effective_tracking_url_display",
                )
            },
        ),
        (
            "Customer & dates",
            {
                "fields": (
                    "notify_customer",
                    "shipped_at",
                    "delivered_at",
                )
            },
        ),
    )

    def effective_carrier(self, obj):
        return obj.effective_tracking_company() if obj.pk else ""

    effective_carrier.short_description = "Carrier (effective)"

    def effective_tracking_url_display(self, obj):
        url = obj.effective_tracking_url() if obj.pk else ""
        if not url:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    effective_tracking_url_display.short_description = "Tracking URL (effective)"


@admin.register(OrderLineItem)
class OrderLineItemAdmin(ModelAdmin):
    list_display = (
        "id",
        "order",
        "product_title",
        "variant_title",
        "quantity",
        "line_total",
        "fulfillment_status",
    )
    readonly_fields = ("created_at", "updated_at")
    search_fields = (
        "product_title",
        "variant_title",
        "sku",
        "order__token",
        "order__id",
        "order__name",
    )
    autocomplete_fields = ("order", "variant")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(ModelAdmin):
    list_display = ("user", "phone", "accepts_marketing", "tax_exempt", "created_at")
    search_fields = ("user__email", "phone")
    raw_id_fields = ("user",)


@admin.register(CustomerAddress)
class CustomerAddressAdmin(ModelAdmin):
    list_display = (
        "user",
        "city",
        "country_code",
        "is_default_shipping",
        "is_default_billing",
        "created_at",
    )
    search_fields = ("user__email", "city", "zip", "address1")
    raw_id_fields = ("user",)


@admin.register(DiscountCode)
class DiscountCodeAdmin(UnfoldImportExportAdmin):
    resource_classes = [DiscountCodeResource]
    list_display = ("code", "discount_type", "value", "usage_count", "usage_limit", "is_active", "created_at")
    search_fields = ("code", "title")


@admin.register(GiftCard)
class GiftCardAdmin(UnfoldImportExportAdmin):
    resource_classes = [GiftCardResource]
    list_display = ("code", "current_balance", "initial_balance", "currency", "is_active", "created_at")
    search_fields = ("code", "note")
