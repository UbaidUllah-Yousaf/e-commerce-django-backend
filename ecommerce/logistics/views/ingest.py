import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from logistics.models.config import FulfillmentConfiguration
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.shipment_manager import ShipmentManager
from logistics.tasks.shipments import process_shipment_pipeline


class LogisticsOrderIngestView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        config = FulfillmentConfiguration.get_solo()
        if not config.ingest_api_token:
            return Response({"detail": "Ingest API not configured."}, status=503)

        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if token != config.ingest_api_token:
            return Response({"detail": "Unauthorized."}, status=401)

        data = request.data
        dto = NormalizedOrderDTO(
            source_platform=data.get("source_platform", "ecommerce"),
            external_order_id=str(data.get("external_order_id", "")),
            order_number=str(data.get("order_number", "")),
            shop_id=data.get("shop_id"),
            ecommerce_order_id=data.get("ecommerce_order_id"),
            customer_payload=data.get("customer", data.get("customer_payload", {})),
            shipping_address=data.get("shipping_address", {}),
            line_items=data.get("line_items", []),
            city=data.get("city", ""),
            cod_amount=data.get("cod_amount"),
        )
        if not dto.external_order_id:
            return Response({"detail": "external_order_id required."}, status=400)

        correlation_id = str(uuid.uuid4())
        shipment = ShipmentManager.upsert_from_dto(dto, correlation_id=correlation_id)
        process_shipment_pipeline.delay(shipment.pk, correlation_id=correlation_id)
        return Response(
            {"shipment_id": shipment.pk, "correlation_id": correlation_id},
            status=status.HTTP_202_ACCEPTED,
        )
