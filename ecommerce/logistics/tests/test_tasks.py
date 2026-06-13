from unittest.mock import patch

from django.test import TestCase, override_settings

from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.models.shipment import Shipment
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.shipment_manager import ShipmentManager
from logistics.tasks.shipments import process_shipment_pipeline


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CeleryTaskTests(TestCase):
    def setUp(self):
        CourierConfiguration.objects.create(courier_name="TCS", is_active=True)
        CityFulfillmentRule.objects.create(
            city_name="*",
            priority=1,
            courier_name="TCS",
            service_type="partner_next_day",
        )

    @patch("logistics.services.quiqup.QuiqupService.create_shipment")
    @patch("logistics.services.fulfillment.FulfillmentSyncService.sync")
    def test_pipeline_task_idempotent_when_fulfilled(self, mock_sync, mock_qq):
        def _fake_create(shipment):
            shipment.quiqup_shipment_id = "q1"
            shipment.save(update_fields=["quiqup_shipment_id", "updated_at"])
            return {"id": "q1"}

        mock_qq.side_effect = _fake_create
        dto = NormalizedOrderDTO(
            source_platform="ecommerce",
            external_order_id="99",
            city="X",
        )
        shipment = ShipmentManager.upsert_from_dto(dto)
        process_shipment_pipeline(shipment.pk)
        shipment.refresh_from_db()
        shipment.processing_state = "fulfilled"
        shipment.save()
        result = process_shipment_pipeline(shipment.pk)
        self.assertEqual(result, "already_fulfilled")
