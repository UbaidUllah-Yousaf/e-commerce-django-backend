from django.test import TestCase, override_settings

from logistics.constants import SOURCE_PLATFORM_ECOMMERCE
from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.models.shipment import Shipment
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.quiqup import QuiqupService
from logistics.services.shipment_manager import ShipmentManager


@override_settings(QUIQUP_USE_MOCK=True)
class QuiqupMockTests(TestCase):
    def setUp(self):
        FulfillmentConfiguration.objects.get_or_create(pk=1)
        CourierConfiguration.objects.create(courier_name="TCS", is_active=True)
        CityFulfillmentRule.objects.create(
            city_name="Lahore",
            priority=1,
            courier_name="TCS",
            service_type="partner_next_day",
        )

    def test_create_shipment_without_credentials(self):
        dto = NormalizedOrderDTO(
            source_platform=SOURCE_PLATFORM_ECOMMERCE,
            external_order_id="mock-1",
            order_number="#1001",
            shipping_address={"city": "Lahore"},
            line_items=[{"title": "Shirt", "quantity": 1}],
            city="Lahore",
        )
        shipment = ShipmentManager.upsert_from_dto(dto)
        ShipmentManager(shipment).run_pipeline(steps=["route", "quiqup"])
        shipment.refresh_from_db()
        self.assertTrue(shipment.quiqup_shipment_id.startswith("mock-"))
        self.assertTrue(shipment.tracking_number.startswith("MOCK-"))

    def test_get_tracking_status(self):
        dto = NormalizedOrderDTO(
            source_platform=SOURCE_PLATFORM_ECOMMERCE,
            external_order_id="mock-2",
            city="Lahore",
        )
        shipment = ShipmentManager.upsert_from_dto(dto)
        QuiqupService().create_shipment(shipment)
        shipment.refresh_from_db()
        data = QuiqupService().get_tracking_status(shipment.quiqup_shipment_id)
        self.assertEqual(data["order"]["status"], "in_transit")
