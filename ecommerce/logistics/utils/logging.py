import logging

logger = logging.getLogger("logistics")


def log_shipment_event(
    message: str,
    *,
    correlation_id: str | None = None,
    shipment_id: int | None = None,
    level: int = logging.INFO,
    **extra,
) -> None:
    payload = dict(extra)
    if correlation_id:
        payload["correlation_id"] = str(correlation_id)
    if shipment_id:
        payload["shipment_id"] = shipment_id
    logger.log(level, message, extra=payload)
