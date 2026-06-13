import json
import uuid

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from logistics.models.config import FulfillmentConfiguration
from logistics.models.shipment import Shipment
from logistics.tasks.shipments import sync_tracking_updates
from logistics.utils.status_mapping import map_quiqup_status


@method_decorator(csrf_exempt, name="dispatch")
class QuiqupTrackingWebhookView(View):
    def post(self, request, *args, **kwargs):
        config = FulfillmentConfiguration.get_solo()
        if config.quiqup_webhook_secret:
            token = request.headers.get("X-Quiqup-Token") or request.headers.get(
                "Authorization", ""
            ).replace("Bearer ", "")
            if token != config.quiqup_webhook_secret:
                return HttpResponseForbidden("Invalid token")

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HttpResponseForbidden("Invalid JSON")

        order_data = payload.get("order") or payload
        reference = (
            order_data.get("reference")
            or order_data.get("id")
            or payload.get("reference")
            or ""
        )
        shipment = None
        if reference:
            shipment = Shipment.objects.filter(idempotency_key=reference).first()
        if not shipment:
            quiqup_id = str(order_data.get("id") or "")
            if quiqup_id:
                shipment = Shipment.objects.filter(quiqup_shipment_id=quiqup_id).first()
        if not shipment:
            return HttpResponse(status=200)

        raw_status = order_data.get("status") or order_data.get("state") or ""
        sync_tracking_updates.delay(
            shipment.pk,
            status=raw_status,
            tracking_number=order_data.get("tracking_number") or "",
            tracking_url=order_data.get("tracking_url") or "",
            raw_payload=payload,
        )
        return HttpResponse(status=200)
