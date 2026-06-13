"""Sync logistics Shipment → ecommerce Fulfillment (Shopify fulfillment records)."""

from __future__ import annotations

import logging

from ecommerce.constants.fulfillment import SHIPMENT_STATUS_IN_TRANSIT, SHIPMENT_STATUS_SUCCESS
from ecommerce.models.fulfillment import Fulfillment, recompute_fulfillment_statuses_for_order
from logistics.constants import (
    LOGISTICS_STATUS_DELIVERED,
    PROCESSING_FULFILLED,
)
from logistics.models.shipment import Shipment
from logistics.utils.fulfillment_mapping import (
    fulfillment_timestamps_for_status,
    map_logistics_to_fulfillment_status,
)

logger = logging.getLogger("logistics.fulfillment")


def fulfillment_status_for_shipment(shipment: Shipment) -> str:
    """Map pipeline + carrier state to Shopify-style Fulfillment.status."""
    if shipment.processing_state == PROCESSING_FULFILLED:
        if shipment.shipment_status == LOGISTICS_STATUS_DELIVERED:
            return SHIPMENT_STATUS_SUCCESS
        if shipment.quiqup_shipment_id or shipment.tracking_number:
            return SHIPMENT_STATUS_IN_TRANSIT
        return SHIPMENT_STATUS_SUCCESS
    return map_logistics_to_fulfillment_status(shipment.shipment_status)


def find_ecommerce_fulfillment(shipment: Shipment) -> Fulfillment | None:
    if not shipment.ecommerce_order_id:
        return None
    linked = Fulfillment.objects.filter(logistics_shipment=shipment).order_by("-id").first()
    if linked:
        return linked
    if shipment.tracking_number:
        match = (
            Fulfillment.objects.filter(
                order_id=shipment.ecommerce_order_id,
                tracking_number=shipment.tracking_number,
            )
            .order_by("-id")
            .first()
        )
        if match:
            return match
    return (
        Fulfillment.objects.filter(order_id=shipment.ecommerce_order_id)
        .order_by("-id")
        .first()
    )


def sync_ecommerce_fulfillment_from_shipment(shipment: Shipment) -> Fulfillment | None:
    """Mirror logistics tracking onto Fulfillment; order status recomputes from line items."""
    fulfillment = find_ecommerce_fulfillment(shipment)
    if not fulfillment:
        return None

    fulfillment_status = fulfillment_status_for_shipment(shipment)
    shipped_at, delivered_at = fulfillment_timestamps_for_status(
        fulfillment_status,
        existing_shipped_at=fulfillment.shipped_at,
        existing_delivered_at=fulfillment.delivered_at,
    )
    update_fields = ["updated_at"]
    if fulfillment.logistics_shipment_id != shipment.pk:
        fulfillment.logistics_shipment = shipment
        update_fields.append("logistics_shipment")
    if fulfillment.status != fulfillment_status:
        fulfillment.status = fulfillment_status
        update_fields.append("status")
    if shipment.tracking_number and fulfillment.tracking_number != shipment.tracking_number:
        fulfillment.tracking_number = shipment.tracking_number
        update_fields.append("tracking_number")
    if shipment.tracking_url and fulfillment.tracking_url != shipment.tracking_url:
        fulfillment.tracking_url = shipment.tracking_url
        update_fields.append("tracking_url")
    if shipment.courier_name and fulfillment.tracking_company != shipment.courier_name:
        fulfillment.tracking_company = shipment.courier_name
        update_fields.append("tracking_company")
    if fulfillment.shipped_at != shipped_at:
        fulfillment.shipped_at = shipped_at
        update_fields.append("shipped_at")
    if fulfillment.delivered_at != delivered_at:
        fulfillment.delivered_at = delivered_at
        update_fields.append("delivered_at")

    fulfillment.save(update_fields=update_fields)
    recompute_fulfillment_statuses_for_order(shipment.ecommerce_order_id)
    return fulfillment


def link_fulfillment_to_shipment(fulfillment: Fulfillment, shipment: Shipment) -> None:
    if fulfillment.logistics_shipment_id == shipment.pk:
        return
    fulfillment.logistics_shipment = shipment
    fulfillment.save(update_fields=["logistics_shipment", "updated_at"])
