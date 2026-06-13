from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from logistics.constants import PROCESSING_FULFILLED, SOURCE_PLATFORM_ECOMMERCE
from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.models.shipment import Shipment
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.shipment_manager import ShipmentManager


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    QUIQUP_BASE_URL="https://platform-api.staging.quiqup.com",
    QUIQUP_CLIENT_ID="test",
    QUIQUP_CLIENT_SECRET="test",
)
class ShipmentManagerTests(TestCase):
    def setUp(self):
        FulfillmentConfiguration.objects.get_or_create(pk=1)
        CourierConfiguration.objects.create(courier_name="TCS", is_active=True)
        CityFulfillmentRule.objects.create(
            city_name="Lahore",
            priority=1,
            courier_name="TCS",
            service_type="partner_next_day",
        )

    def _dto(self, external_id="1001"):
        return NormalizedOrderDTO(
            source_platform=SOURCE_PLATFORM_ECOMMERCE,
            external_order_id=external_id,
            order_number="#1001",
            shipping_address={"city": "Lahore"},
            line_items=[{"title": "Shirt", "quantity": 1}],
            city="Lahore",
        )

    def test_idempotent_upsert(self):
        s1 = ShipmentManager.upsert_from_dto(self._dto("dup-1"))
        s2 = ShipmentManager.upsert_from_dto(self._dto("dup-1"))
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(Shipment.objects.filter(idempotency_key=s1.idempotency_key).count(), 1)

    @patch("logistics.services.quiqup.QuiqupService.create_shipment")
    @patch("logistics.services.fulfillment.FulfillmentSyncService.sync")
    def test_pipeline_routes_and_fulfills(self, mock_sync, mock_quiqup):
        def _fake_create(shipment):
            shipment.quiqup_shipment_id = "qq-1"
            shipment.tracking_number = "TRK1"
            shipment.save(
                update_fields=["quiqup_shipment_id", "tracking_number", "updated_at"]
            )
            return {"id": "qq-1", "tracking_number": "TRK1"}

        mock_quiqup.side_effect = _fake_create
        shipment = ShipmentManager.upsert_from_dto(self._dto("pipe-1"))
        ShipmentManager(shipment).run_pipeline()
        shipment.refresh_from_db()
        self.assertEqual(shipment.courier_name, "TCS")
        self.assertEqual(shipment.quiqup_shipment_id, "qq-1")
        self.assertEqual(shipment.processing_state, PROCESSING_FULFILLED)
        mock_sync.assert_called_once()
