from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ecommerce.router import get_api_routes
from ecommerce.views.customer import CustomerProfileMeView
from ecommerce.views.size_chart import SizeChartByTagView
from ecommerce.views.stripe import (
    StripeConfigView,
    StripeSessionConfirmView,
    StripeWebhookView,
)

router = DefaultRouter()
get_api_routes(router)

urlpatterns = [
    path("api/v1/customers/me/", CustomerProfileMeView.as_view()),
    path("api/v1/size-charts/by-tag/", SizeChartByTagView.as_view(), name="size-chart-by-tag"),
    path("api/v1/stripe/config/", StripeConfigView.as_view(), name="stripe-config"),
    path("api/v1/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path(
        "api/v1/stripe/session/<str:session_id>/confirm/",
        StripeSessionConfirmView.as_view(),
        name="stripe-session-confirm",
    ),
    path("api/v1/", include(router.urls)),
]