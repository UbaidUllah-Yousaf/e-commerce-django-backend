from __future__ import annotations

import uuid

from django.db import transaction

from logistics.constants import (
    DEFAULT_PIPELINE_STEPS,
    LOGISTICS_TERMINAL_STATUSES,
    PIPELINE_STEP_FULFILL,
    PIPELINE_STEP_QUIQUP,
    PIPELINE_STEP_ROUTE,
    PROCESSING_FAILED,
    PROCESSING_FULFILLED,
    PROCESSING_RECEIVED,
    PROCESSING_ROUTING,
    PROCESSING_SHIPMENT_CREATED,
)
from logistics.models.config import FulfillmentConfiguration
from logistics.models.shipment import Shipment, ShipmentStatusHistory
from logistics.rules.city_router import CityRouterError, select_courier
from logistics.services.dto import NormalizedOrderDTO
from logistics.services.fulfillment import FulfillmentSyncService
from logistics.services.quiqup import QuiqupAPIError, QuiqupService
from logistics.utils.city import extract_city_from_address
from logistics.utils.idempotency import build_idempotency_key
from logistics.utils.logging import log_shipment_event


class ShipmentManagerError(Exception):
    pass


class ShipmentManager:
    def __init__(self, shipment: Shipment) -> None:
        self.shipment = shipment
        self.config = FulfillmentConfiguration.get_solo()

    @classmethod
    def upsert_from_dto(cls, dto: NormalizedOrderDTO, *, correlation_id: str | None = None) -> Shipment:
        key = build_idempotency_key(
            dto.source_platform,
            dto.external_order_id,
            dto.shop_id,
        )
        city = dto.city or extract_city_from_address(dto.shipping_address)
        defaults = {
            "source_platform": dto.source_platform,
            "shop_id": dto.shop_id,
            "ecommerce_order_id": dto.ecommerce_order_id,
            "external_order_id": dto.external_order_id,
            "order_number": dto.order_number,
            "customer_payload": dto.customer_payload,
            "shipping_address": dto.shipping_address,
            "line_items": dto.line_items,
            "city": city,
            "cod_amount": dto.cod_amount,
            "correlation_id": uuid.UUID(correlation_id) if correlation_id else uuid.uuid4(),
        }
        shipment, created = Shipment.objects.get_or_create(
            idempotency_key=key,
            defaults=defaults,
        )
        if not created:
            for field, value in defaults.items():
                if field != "correlation_id":
                    setattr(shipment, field, value)
            shipment.save()
        log_shipment_event(
            "Shipment upserted",
            correlation_id=str(shipment.correlation_id),
            shipment_id=shipment.pk,
            was_created=created,
        )
        return shipment

    def run_pipeline(self, steps: list[str] | None = None) -> None:
        steps = steps or list(DEFAULT_PIPELINE_STEPS)
        with transaction.atomic():
            shipment = Shipment.objects.select_for_update().get(pk=self.shipment.pk)
            self.shipment = shipment

            if PIPELINE_STEP_ROUTE in steps:
                self._step_route()
            if PIPELINE_STEP_QUIQUP in steps:
                self._step_quiqup()
            if PIPELINE_STEP_FULFILL in steps:
                self._step_fulfill()

    def _step_route(self) -> None:
        if self.shipment.processing_state in (
            PROCESSING_SHIPMENT_CREATED,
            PROCESSING_FULFILLED,
        ) and self.shipment.courier_name:
            return
        self.shipment.processing_state = PROCESSING_ROUTING
        self.shipment.save(update_fields=["processing_state", "updated_at"])
        try:
            selection = select_courier(
                self.shipment.city,
                courier_override=self.shipment.courier_override,
            )
        except CityRouterError as exc:
            self._fail(str(exc))
            raise ShipmentManagerError(str(exc)) from exc

        self.shipment.courier_name = selection.courier_name
        self.shipment.service_type = selection.service_type
        self.shipment.save(
            update_fields=["courier_name", "service_type", "processing_state", "updated_at"]
        )
        log_shipment_event(
            "Courier selected",
            correlation_id=str(self.shipment.correlation_id),
            shipment_id=self.shipment.pk,
            courier=selection.courier_name,
        )

    def _step_quiqup(self) -> None:
        if self.shipment.quiqup_shipment_id:
            if self.shipment.processing_state != PROCESSING_FULFILLED:
                self.shipment.processing_state = PROCESSING_SHIPMENT_CREATED
                self.shipment.save(update_fields=["processing_state", "updated_at"])
            return
        if not self.shipment.courier_name:
            self._step_route()

        try:
            QuiqupService().create_shipment(self.shipment)
        except QuiqupAPIError as exc:
            self._fail(str(exc))
            raise ShipmentManagerError(str(exc)) from exc

        self.shipment.refresh_from_db()
        self.shipment.processing_state = PROCESSING_SHIPMENT_CREATED
        self.shipment.error_message = ""
        self.shipment.save(update_fields=["processing_state", "error_message", "updated_at"])

    def _step_fulfill(self) -> None:
        from logistics.services.ecommerce_fulfillment_sync import (
            sync_ecommerce_fulfillment_from_shipment,
        )

        if self.shipment.processing_state == PROCESSING_FULFILLED:
            sync_ecommerce_fulfillment_from_shipment(self.shipment)
            return
        if self.config.auto_fulfill_enabled:
            try:
                FulfillmentSyncService(self.shipment).sync()
            except Exception as exc:
                self._fail(str(exc))
                raise ShipmentManagerError(str(exc)) from exc
        else:
            sync_ecommerce_fulfillment_from_shipment(self.shipment)

        self.shipment.processing_state = PROCESSING_FULFILLED
        self.shipment.save(update_fields=["processing_state", "updated_at"])

    def _fail(self, message: str) -> None:
        self.shipment.processing_state = PROCESSING_FAILED
        self.shipment.error_message = message[:2000]
        self.shipment.retry_count += 1
        self.shipment.save(
            update_fields=["processing_state", "error_message", "retry_count", "updated_at"]
        )

    @classmethod
    def retry(cls, shipment_id: int, steps: list[str] | None = None) -> None:
        shipment = Shipment.objects.get(pk=shipment_id)
        config = FulfillmentConfiguration.get_solo()
        if shipment.retry_count >= config.max_retry_count:
            raise ShipmentManagerError("Max retry count exceeded.")
        cls(shipment).run_pipeline(steps=steps)

    def apply_tracking_update(
        self,
        status: str,
        *,
        tracking_number: str = "",
        tracking_url: str = "",
        source: str = "quiqup_webhook",
        raw_payload: dict | None = None,
    ) -> None:
        from logistics.constants import STATUS_HISTORY_QUIQUP_WEBHOOK

        changed = False
        if status and status != self.shipment.shipment_status:
            self.shipment.shipment_status = status
            changed = True
            ShipmentStatusHistory.objects.create(
                shipment=self.shipment,
                status=status,
                source=source,
                raw_payload=raw_payload or {},
            )
        if tracking_number and tracking_number != self.shipment.tracking_number:
            self.shipment.tracking_number = tracking_number
            changed = True
        if tracking_url and tracking_url != self.shipment.tracking_url:
            self.shipment.tracking_url = tracking_url
            changed = True
        if changed:
            self.shipment.save(
                update_fields=[
                    "shipment_status",
                    "tracking_number",
                    "tracking_url",
                    "updated_at",
                ]
            )
        if self.config.tracking_sync_enabled:
            FulfillmentSyncService(self.shipment).sync_tracking_only()
