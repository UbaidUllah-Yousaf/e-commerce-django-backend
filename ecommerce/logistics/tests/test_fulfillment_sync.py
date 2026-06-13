import uuid

from django.db.models.signals import post_save
from django.test import TestCase, override_settings

from ecommerce.constants.fulfillment import (
    FULFILLMENT_STATUS_FULFILLED,
    SHIPMENT_STATUS_IN_TRANSIT,
    SHIPMENT_STATUS_SUCCESS,
)
from ecommerce.models.checkout import Checkout, Order
from ecommerce.models.fulfillment import Fulfillment, FulfillmentService
from logistics.constants import (
    LOGISTICS_STATUS_DELIVERED,
    LOGISTICS_STATUS_IN_TRANSIT,
    PROCESSING_FULFILLED,
    SOURCE_PLATFORM_ECOMMERCE,
)
from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.ecommerce_fulfillment_sync import (
    fulfillment_status_for_shipment,
    sync_ecommerce_fulfillment_from_shipment,
)
from logistics.services.shipment_manager import ShipmentManager


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    QUIQUP_USE_MOCK=True,
)
class FulfillmentStatusSyncTests(TestCase):
    def setUp(self):
        from logistics.signals import enqueue_logistics_for_new_order

        post_save.disconnect(enqueue_logistics_for_new_order, sender=Order)
        self.addCleanup(
            post_save.connect,
            enqueue_logistics_for_new_order,
            sender=Order,
        )
        FulfillmentConfiguration.objects.get_or_create(pk=1)
        CourierConfiguration.objects.create(courier_name="TCS", is_active=True)
        CityFulfillmentRule.objects.create(
            city_name="Lahore",
            priority=1,
            courier_name="TCS",
            service_type="partner_next_day",
        )

    def _shipment_with_fulfillment(self):
        checkout = Checkout.objects.create(token=uuid.uuid4(), status="complete")
        order = Order.objects.create(
            checkout=checkout,
            order_number=9001,
            name="#9001",
            token=uuid.uuid4(),
            email="sync@test.com",
            currency="USD",
            subtotal="10",
            discount_amount="0",
            shipping_total="0",
            tax_total="0",
            gift_card_total="0",
            total="10",
        )
        dto = NormalizedOrderDTO(
            source_platform=SOURCE_PLATFORM_ECOMMERCE,
            external_order_id=str(order.pk),
            order_number=order.name,
            ecommerce_order_id=order.pk,
            city="Lahore",
            line_items=[{"title": "Item", "quantity": 1}],
        )
        shipment = ShipmentManager.upsert_from_dto(dto)
        shipment.quiqup_shipment_id = "mock-abc"
        shipment.tracking_number = "TRK-SYNC"
        shipment.tracking_url = "https://track.example/TRK-SYNC"
        shipment.shipment_status = LOGISTICS_STATUS_IN_TRANSIT
        shipment.courier_name = "TCS"
        shipment.processing_state = PROCESSING_FULFILLED
        shipment.save()
        svc = FulfillmentService.objects.create(name="TCS", courier_name="TCS")
        fulfillment = Fulfillment.objects.create(
            order=order,
            fulfillment_service=svc,
            status=SHIPMENT_STATUS_IN_TRANSIT,
            tracking_number="TRK-SYNC",
            logistics_shipment=shipment,
        )
        return shipment, order, fulfillment

    def test_fulfilled_pipeline_maps_to_success(self):
        checkout = Checkout.objects.create(token=uuid.uuid4(), status="complete")
        order = Order.objects.create(
            checkout=checkout,
            order_number=9002,
            name="#9002",
            token=uuid.uuid4(),
            email="x@test.com",
            currency="USD",
            subtotal="10",
            discount_amount="0",
            shipping_total="0",
            tax_total="0",
            gift_card_total="0",
            total="10",
        )
        dto = NormalizedOrderDTO(
            source_platform=SOURCE_PLATFORM_ECOMMERCE,
            external_order_id=str(order.pk),
            ecommerce_order_id=order.pk,
            city="Lahore",
        )
        shipment = ShipmentManager.upsert_from_dto(dto)
        shipment.processing_state = PROCESSING_FULFILLED
        shipment.quiqup_shipment_id = "mock-xyz"
        self.assertEqual(fulfillment_status_for_shipment(shipment), SHIPMENT_STATUS_IN_TRANSIT)
        shipment.shipment_status = LOGISTICS_STATUS_DELIVERED
        self.assertEqual(fulfillment_status_for_shipment(shipment), SHIPMENT_STATUS_SUCCESS)

    def test_tracking_update_syncs_fulfillment_status(self):
        shipment, order, fulfillment = self._shipment_with_fulfillment()
        shipment.shipment_status = LOGISTICS_STATUS_DELIVERED
        shipment.save(update_fields=["shipment_status", "updated_at"])
        sync_ecommerce_fulfillment_from_shipment(shipment)
        fulfillment.refresh_from_db()
        self.assertEqual(fulfillment.status, SHIPMENT_STATUS_SUCCESS)
