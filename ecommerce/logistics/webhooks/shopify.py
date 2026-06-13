import json
import uuid

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from logistics.constants import SOURCE_PLATFORM_SHOPIFY
from logistics.models.shipment import WebhookLog
from logistics.models.shopify import ShopifyConfiguration
from logistics.tasks.shipments import process_shopify_order_webhook
from logistics.utils.hmac import verify_shopify_hmac


@method_decorator(csrf_exempt, name="dispatch")
class ShopifyOrderCreateWebhookView(View):
    def post(self, request, *args, **kwargs):
        shop_domain = request.headers.get("X-Shopify-Shop-Domain", "").strip().lower()
        if not shop_domain:
            return HttpResponseForbidden("Missing shop domain")

        shop = ShopifyConfiguration.objects.filter(
            shop_domain__iexact=shop_domain,
            is_active=True,
        ).first()
        if not shop:
            return HttpResponseForbidden("Unknown or inactive store")

        hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
        body = request.body
        if not verify_shopify_hmac(body, shop.webhook_secret, hmac_header):
            return HttpResponseForbidden("Invalid HMAC")

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HttpResponseForbidden("Invalid JSON")

        correlation_id = uuid.uuid4()
        log = WebhookLog.objects.create(
            shop=shop,
            source_platform=SOURCE_PLATFORM_SHOPIFY,
            event_type="orders/create",
            payload=payload,
            correlation_id=correlation_id,
        )
        process_shopify_order_webhook.delay(log.pk, correlation_id=str(correlation_id))
        return HttpResponse(status=200)
