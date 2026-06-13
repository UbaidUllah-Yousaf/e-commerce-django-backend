"""In-memory Quiqup API responses for local development."""

from __future__ import annotations

import uuid
from typing import Any

_MOCK_ORDERS: dict[str, dict[str, Any]] = {}


def reset_mock_orders() -> None:
    _MOCK_ORDERS.clear()


def create_mock_order(payload: dict[str, Any]) -> dict[str, Any]:
    reference = payload.get("reference") or ""
    order_id = f"mock-{uuid.uuid4().hex[:12]}"
    tracking_number = f"MOCK-{order_id[5:13].upper()}"
    order = {
        "id": order_id,
        "reference": reference,
        "service_kind": payload.get("service_kind", "partner_next_day"),
        "status": "created",
        "tracking_number": tracking_number,
        "tracking_url": f"https://track.example.com/{tracking_number}",
    }
    _MOCK_ORDERS[order_id] = order
    if reference:
        _MOCK_ORDERS[reference] = order
    return {"order": order}


def get_mock_order(order_id: str) -> dict[str, Any]:
    order = _MOCK_ORDERS.get(order_id)
    if not order:
        raise KeyError(order_id)
    stored = dict(order)
    if stored.get("status") == "created":
        stored["status"] = "in_transit"
    return {"order": stored}
