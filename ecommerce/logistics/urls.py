from django.conf import settings
from django.urls import path

from logistics.webhooks.quiqup import QuiqupTrackingWebhookView
from logistics.webhooks.shopify import ShopifyOrderCreateWebhookView

urlpatterns = [
    path(
        "webhooks/shopify/orders-create/",
        ShopifyOrderCreateWebhookView.as_view(),
        name="logistics-shopify-orders-create",
    ),
    path(
        "webhooks/quiqup/",
        QuiqupTrackingWebhookView.as_view(),
        name="logistics-quiqup-webhook",
    ),
]

if settings.DEBUG:
    from logistics.mock.quiqup_views import (
        MockQuiqupCreateOrderView,
        MockQuiqupOAuthView,
        MockQuiqupOrderDetailView,
    )
    from logistics.views.ingest import LogisticsOrderIngestView

    urlpatterns = [
        path("mock/quiqup/oauth/token", MockQuiqupOAuthView.as_view(), name="logistics-mock-quiqup-oauth"),
        path(
            "mock/quiqup/api/fulfilment/orders",
            MockQuiqupCreateOrderView.as_view(),
            name="logistics-mock-quiqup-orders",
        ),
        path(
            "mock/quiqup/api/fulfilment/orders/<str:order_id>",
            MockQuiqupOrderDetailView.as_view(),
            name="logistics-mock-quiqup-order-detail",
        ),
        path(
            "orders/ingest/",
            LogisticsOrderIngestView.as_view(),
            name="logistics-order-ingest",
        ),
        *urlpatterns,
    ]
