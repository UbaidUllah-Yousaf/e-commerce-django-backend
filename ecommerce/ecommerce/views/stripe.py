from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.serializers.stripe import StripeConfigSerializer
from ecommerce.services.checkout_payment_settings import (
    cod_complete_allowed,
    get_checkout_payment_settings,
    get_effective_checkout_redirect_urls,
    get_stripe_status,
    stripe_checkout_available,
    stripe_unavailable_reason,
)
from ecommerce.services.stripe_checkout import (
    StripeCheckoutError,
    fulfill_checkout_from_stripe_session,
    handle_stripe_webhook_event,
    stripe_enabled,
)


class StripeConfigView(APIView):
    """GET /api/v1/stripe/config/ — publishable key for Stripe.js / redirect flows."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: StripeConfigSerializer})
    def get(self, request):
        opts = get_checkout_payment_settings()
        urls = get_effective_checkout_redirect_urls()
        stripe_status = get_stripe_status()
        return Response(
            {
                "enabled": stripe_checkout_available(),
                "publishable_key": getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "",
                "stripe": stripe_status,
                "payment_options": {
                    "stripe_checkout": stripe_status["stripe_checkout_enabled"],
                    "stripe_checkout_available": stripe_status["stripe_checkout_available"],
                    "stripe_keys_configured": stripe_status["stripe_keys_configured"],
                    "stripe_unavailable_reason": stripe_status["unavailable_reason"],
                    "cod": cod_complete_allowed(),
                    "zero_total_complete": True,
                    "default_success_url": opts.default_success_url or "",
                    "default_cancel_url": opts.default_cancel_url or "",
                    "generated_checkout_urls": {
                        "success_url": urls["generated_success_url"],
                        "cancel_url": urls["generated_cancel_url"],
                    },
                    "effective_checkout_urls": {
                        "success_url": urls["success_url"],
                        "cancel_url": urls["cancel_url"],
                    },
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/v1/stripe/webhook/

    Stripe sends events here. Configure in Dashboard → Developers → Webhooks.
  Required events: ``checkout.session.completed``, ``checkout.session.expired``.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            result = handle_stripe_webhook_event(request.body, sig)
        except StripeCheckoutError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse(status=200, content=result)


class StripeSessionConfirmView(APIView):
    """
    GET /api/v1/stripe/session/{session_id}/confirm/

    Optional polling after redirect: completes the order if webhook has not run yet.
    """

    permission_classes = [AllowAny]

    def get(self, request, session_id):
        if not stripe_enabled():
            return Response(
                {"detail": stripe_unavailable_reason() or "Stripe is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            order = fulfill_checkout_from_stripe_session(session_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if order is None:
            return Response(
                {"detail": "Payment session not found or not paid."},
                status=status.HTTP_404_NOT_FOUND,
            )
        from ecommerce.serializers.checkout import OrderSerializer

        return Response(OrderSerializer(order).data)
