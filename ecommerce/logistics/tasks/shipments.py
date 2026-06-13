from __future__ import annotations

import logging
import uuid

import requests
from celery import shared_task
from django.db import transaction

from logistics.constants import (
    DEFAULT_PIPELINE_STEPS,
    PIPELINE_STEP_FULFILL,
    PIPELINE_STEP_QUIQUP,
    SOURCE_PLATFORM_SHOPIFY,
)
from logistics.models.config import FulfillmentConfiguration
from logistics.models.shipment import Shipment, WebhookLog
from logistics.models.shopify import ShopifyConfiguration
from logistics.services.parsers import parse_ecommerce_order, parse_shopify_order
from logistics.services.quiqup import QuiqupAPIError
from logistics.services.shipment_manager import ShipmentManager, ShipmentManagerError
from logistics.utils.logging import log_shipment_event
from logistics.utils.status_mapping import map_quiqup_status

logger = logging.getLogger("logistics.tasks")


@shared_task(
    bind=True,
    acks_late=True,
    autoretry_for=(requests.RequestException, QuiqupAPIError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    name="logistics.process_shipment_pipeline",
)
def process_shipment_pipeline(
    self,
    shipment_id: int,
    correlation_id: str | None = None,
    steps: list[str] | None = None,
) -> str:
    shipment = Shipment.objects.filter(pk=shipment_id).first()
    if not shipment:
        return "missing"
    shipment.last_celery_task_id = self.request.id or ""
    shipment.save(update_fields=["last_celery_task_id", "updated_at"])

    if shipment.processing_state == "fulfilled" and not steps:
        return "already_fulfilled"

    try:
        ShipmentManager(shipment).run_pipeline(steps=steps or list(DEFAULT_PIPELINE_STEPS))
    except ShipmentManagerError as exc:
        log_shipment_event(
            str(exc),
            correlation_id=correlation_id or str(shipment.correlation_id),
            shipment_id=shipment_id,
            level=logging.ERROR,
        )
        raise
    return "ok"


@shared_task(bind=True, acks_late=True, name="logistics.process_shopify_order_webhook")
def process_shopify_order_webhook(
    self,
    webhook_log_id: int,
    correlation_id: str | None = None,
) -> str:
    log = WebhookLog.objects.select_related("shop").filter(pk=webhook_log_id).first()
    if not log or not log.shop:
        return "invalid_log"

    try:
        dto = parse_shopify_order(log.payload, log.shop_id)
        shipment = ShipmentManager.upsert_from_dto(
            dto,
            correlation_id=correlation_id or str(log.correlation_id),
        )
        process_shipment_pipeline.delay(
            shipment.pk,
            correlation_id=str(shipment.correlation_id),
        )
        log.processed = True
        log.error_message = ""
        log.save(update_fields=["processed", "error_message", "updated_at"])
    except Exception as exc:
        log.processed = False
        log.error_message = str(exc)[:2000]
        log.save(update_fields=["processed", "error_message", "updated_at"])
        raise
    return "ok"


@shared_task(bind=True, acks_late=True, name="logistics.process_custom_order")
def process_custom_order(
    self,
    order_id: int,
    correlation_id: str | None = None,
) -> str:
    from ecommerce.models.checkout import Order

    order = (
        Order.objects.prefetch_related("line_items")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return "missing_order"

    dto = parse_ecommerce_order(order)
    shipment = ShipmentManager.upsert_from_dto(
        dto,
        correlation_id=correlation_id or str(uuid.uuid4()),
    )
    process_shipment_pipeline.delay(
        shipment.pk,
        correlation_id=str(shipment.correlation_id),
    )
    return "ok"


@shared_task(bind=True, acks_late=True, name="logistics.create_quiqup_shipment")
def create_quiqup_shipment(self, shipment_id: int, correlation_id: str | None = None) -> str:
    process_shipment_pipeline.delay(
        shipment_id,
        correlation_id=correlation_id,
        steps=[PIPELINE_STEP_QUIQUP],
    )
    return "enqueued"


@shared_task(bind=True, acks_late=True, name="logistics.apply_auto_fulfillment_rules")
def apply_auto_fulfillment_rules(self, shipment_id: int, correlation_id: str | None = None) -> str:
    process_shipment_pipeline.delay(
        shipment_id,
        correlation_id=correlation_id,
        steps=[PIPELINE_STEP_FULFILL],
    )
    return "enqueued"


@shared_task(bind=True, acks_late=True, name="logistics.sync_tracking_updates")
def sync_tracking_updates(
    self,
    shipment_id: int,
    status: str = "",
    tracking_number: str = "",
    tracking_url: str = "",
    raw_payload: dict | None = None,
    source: str = "quiqup_webhook",
) -> str:
    shipment = Shipment.objects.filter(pk=shipment_id).first()
    if not shipment:
        return "missing"
    mapped = map_quiqup_status(status) if status else shipment.shipment_status
    ShipmentManager(shipment).apply_tracking_update(
        mapped,
        tracking_number=tracking_number,
        tracking_url=tracking_url,
        source=source,
        raw_payload=raw_payload,
    )
    config = FulfillmentConfiguration.get_solo()
    if config.auto_fulfill_enabled and shipment.processing_state != "fulfilled":
        apply_auto_fulfillment_rules.delay(shipment_id)
    return "ok"


@shared_task(name="logistics.poll_quiqup_tracking_batch")
def poll_quiqup_tracking_batch() -> str:
    from logistics.constants import LOGISTICS_TERMINAL_STATUSES
    from logistics.services.quiqup import QuiqupService

    qs = Shipment.objects.exclude(shipment_status__in=LOGISTICS_TERMINAL_STATUSES).exclude(
        quiqup_shipment_id=""
    )[:100]
    service = QuiqupService()
    count = 0
    for shipment in qs:
        try:
            data = service.get_tracking_status(shipment.quiqup_shipment_id)
            order_data = data.get("order") or data
            raw_status = order_data.get("status") or order_data.get("state") or ""
            sync_tracking_updates.delay(
                shipment.pk,
                status=raw_status,
                tracking_number=order_data.get("tracking_number") or shipment.tracking_number,
                tracking_url=order_data.get("tracking_url") or shipment.tracking_url,
                raw_payload=data,
                source="quiqup_poll",
            )
            count += 1
        except Exception as exc:
            logger.warning("Poll failed for shipment %s: %s", shipment.pk, exc)
    return f"polled_{count}"
