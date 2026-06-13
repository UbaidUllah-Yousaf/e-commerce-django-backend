from __future__ import annotations

import logging

from ecommerce.constants.fulfillment import FULFILLMENT_CREATE_SCOPE_COMPLETE
from ecommerce.models.fulfillment import Fulfillment, FulfillmentService
from ecommerce.services.fulfillment_ops import FulfillmentCreateError, create_order_fulfillment
from logistics.constants import SOURCE_PLATFORM_ECOMMERCE, SOURCE_PLATFORM_SHOPIFY
from logistics.models.config import FulfillmentConfiguration
from logistics.models.shipment import Shipment
from logistics.services.ecommerce_fulfillment_sync import (
    find_ecommerce_fulfillment,
    fulfillment_status_for_shipment,
    link_fulfillment_to_shipment,
    sync_ecommerce_fulfillment_from_shipment,
)
from logistics.services.shopify import ShopifyAPIError, ShopifyService

logger = logging.getLogger("logistics.fulfillment")


class FulfillmentSyncService:
    def __init__(self, shipment: Shipment) -> None:
        self.shipment = shipment
        self.config = FulfillmentConfiguration.get_solo()

    def sync(self) -> None:
        if not self.config.auto_fulfill_enabled:
            return
        if self.shipment.source_platform == SOURCE_PLATFORM_ECOMMERCE:
            self._sync_ecommerce()
        elif self.shipment.source_platform == SOURCE_PLATFORM_SHOPIFY:
            self._sync_shopify()

    def _sync_ecommerce(self) -> None:
        order = self.shipment.ecommerce_order
        if not order:
            return
        existing = find_ecommerce_fulfillment(self.shipment)
        if existing:
            link_fulfillment_to_shipment(existing, self.shipment)
            sync_ecommerce_fulfillment_from_shipment(self.shipment)
            return

        svc = FulfillmentService.objects.filter(
            courier_name=self.shipment.courier_name,
            is_active=True,
        ).first()
        if not svc:
            svc, _ = FulfillmentService.objects.get_or_create(
                name=f"{self.shipment.courier_name} (auto)",
                courier_name=self.shipment.courier_name,
                defaults={"is_active": True},
            )

        try:
            fulfillment = create_order_fulfillment(
                order,
                scope=FULFILLMENT_CREATE_SCOPE_COMPLETE,
                manual=False,
                fulfillment_service=svc,
                name="Auto logistics fulfillment",
                notify_customer=True,
                tracking_company=self.shipment.courier_name,
                tracking_number=self.shipment.tracking_number or "",
                tracking_url=self.shipment.tracking_url or "",
                status=fulfillment_status_for_shipment(self.shipment),
                line_items=None,
            )
            link_fulfillment_to_shipment(fulfillment, self.shipment)
            sync_ecommerce_fulfillment_from_shipment(self.shipment)
        except FulfillmentCreateError as exc:
            logger.warning("Ecommerce fulfillment skipped: %s", exc)

    def _sync_shopify(self) -> None:
        shop = self.shipment.shop
        if not shop:
            return
        try:
            ShopifyService(shop).create_fulfillment(
                self.shipment.external_order_id,
                tracking_number=self.shipment.tracking_number or "",
                tracking_company=self.shipment.courier_name or "",
                tracking_url=self.shipment.tracking_url or "",
            )
        except ShopifyAPIError as exc:
            logger.error("Shopify fulfillment failed: %s", exc)
            raise

    def sync_tracking_only(self) -> None:
        if not self.config.tracking_sync_enabled:
            return
        if self.shipment.source_platform == SOURCE_PLATFORM_ECOMMERCE:
            sync_ecommerce_fulfillment_from_shipment(self.shipment)
