"""Map logistics carrier status ↔ ecommerce Fulfillment.status."""

from __future__ import annotations

from django.utils import timezone

from ecommerce.constants.fulfillment import (
    SHIPMENT_STATUS_CANCELLED,
    SHIPMENT_STATUS_ERROR,
    SHIPMENT_STATUS_FAILURE,
    SHIPMENT_STATUS_IN_TRANSIT,
    SHIPMENT_STATUS_OPEN,
    SHIPMENT_STATUS_PENDING,
    SHIPMENT_STATUS_SUCCESS,
)
from logistics.constants import (
    LOGISTICS_STATUS_CHOICES,
    LOGISTICS_STATUS_DELIVERED,
    LOGISTICS_STATUS_FAILED_DELIVERY,
    LOGISTICS_STATUS_IN_TRANSIT,
    LOGISTICS_STATUS_OUT_FOR_DELIVERY,
    LOGISTICS_STATUS_PENDING,
    LOGISTICS_STATUS_PICKED_UP,
    LOGISTICS_STATUS_RETURNED,
)
FULFILLMENT_TO_LOGISTICS = {
    SHIPMENT_STATUS_PENDING: LOGISTICS_STATUS_PENDING,
    SHIPMENT_STATUS_OPEN: LOGISTICS_STATUS_PENDING,
    SHIPMENT_STATUS_IN_TRANSIT: LOGISTICS_STATUS_IN_TRANSIT,
    SHIPMENT_STATUS_SUCCESS: LOGISTICS_STATUS_DELIVERED,
    SHIPMENT_STATUS_CANCELLED: LOGISTICS_STATUS_RETURNED,
    SHIPMENT_STATUS_ERROR: LOGISTICS_STATUS_FAILED_DELIVERY,
    SHIPMENT_STATUS_FAILURE: LOGISTICS_STATUS_FAILED_DELIVERY,
}

LOGISTICS_TO_FULFILLMENT_STATUS = {
    LOGISTICS_STATUS_PENDING: SHIPMENT_STATUS_PENDING,
    LOGISTICS_STATUS_PICKED_UP: SHIPMENT_STATUS_IN_TRANSIT,
    LOGISTICS_STATUS_IN_TRANSIT: SHIPMENT_STATUS_IN_TRANSIT,
    LOGISTICS_STATUS_OUT_FOR_DELIVERY: SHIPMENT_STATUS_IN_TRANSIT,
    LOGISTICS_STATUS_DELIVERED: SHIPMENT_STATUS_SUCCESS,
    LOGISTICS_STATUS_FAILED_DELIVERY: SHIPMENT_STATUS_FAILURE,
    LOGISTICS_STATUS_RETURNED: SHIPMENT_STATUS_CANCELLED,
}

def map_fulfillment_to_logistics_status(fulfillment_status: str) -> str:
    return FULFILLMENT_TO_LOGISTICS.get(fulfillment_status, LOGISTICS_STATUS_PENDING)


def map_logistics_to_fulfillment_status(logistics_status: str) -> str:
    return LOGISTICS_TO_FULFILLMENT_STATUS.get(
        logistics_status,
        SHIPMENT_STATUS_PENDING,
    )


def fulfillment_timestamps_for_status(fulfillment_status: str, *, existing_shipped_at, existing_delivered_at):
    now = timezone.now()
    shipped_at = existing_shipped_at
    delivered_at = existing_delivered_at
    if fulfillment_status == SHIPMENT_STATUS_SUCCESS:
        shipped_at = shipped_at or now
        delivered_at = delivered_at or now
    elif fulfillment_status == SHIPMENT_STATUS_IN_TRANSIT:
        shipped_at = shipped_at or now
    return shipped_at, delivered_at
