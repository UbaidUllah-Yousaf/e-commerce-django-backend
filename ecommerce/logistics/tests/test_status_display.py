from django.test import TestCase

from logistics.constants import (
    LOGISTICS_STATUS_DELIVERED,
    LOGISTICS_STATUS_IN_TRANSIT,
    PROCESSING_FULFILLED,
    PROCESSING_SHIPMENT_CREATED,
)
from logistics.models.shipment import Shipment
from logistics.utils.status_display import (
    processing_timeline,
    processing_state_label,
    shipment_status_view,
)


class StatusDisplayTests(TestCase):
    def test_processing_labels_shopify_style(self):
        self.assertEqual(processing_state_label("routing"), "Preparing shipment")
        self.assertEqual(processing_state_label("shipment_created"), "Ready to ship")

    def test_timeline_marks_current_step(self):
        steps = processing_timeline(PROCESSING_SHIPMENT_CREATED)
        current = [s for s in steps if s["current"]]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["key"], PROCESSING_SHIPMENT_CREATED)

    def test_delivered_headline(self):
        shipment = Shipment(
            processing_state=PROCESSING_FULFILLED,
            shipment_status=LOGISTICS_STATUS_DELIVERED,
        )
        view = shipment_status_view(shipment)
        self.assertEqual(view.headline, "Delivered")

    def test_in_transit_headline(self):
        shipment = Shipment(
            processing_state=PROCESSING_FULFILLED,
            shipment_status=LOGISTICS_STATUS_IN_TRANSIT,
        )
        view = shipment_status_view(shipment)
        self.assertEqual(view.headline, "In transit")
