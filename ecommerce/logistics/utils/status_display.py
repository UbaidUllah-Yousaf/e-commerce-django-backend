"""Shopify-style labels, badges, and summaries for logistics statuses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils.html import format_html

from logistics.constants import (
    LOGISTICS_STATUS_DELIVERED,
    LOGISTICS_STATUS_FAILED_DELIVERY,
    LOGISTICS_STATUS_IN_TRANSIT,
    LOGISTICS_STATUS_OUT_FOR_DELIVERY,
    LOGISTICS_STATUS_PENDING,
    LOGISTICS_STATUS_PICKED_UP,
    LOGISTICS_STATUS_RETURNED,
    PROCESSING_FAILED,
    PROCESSING_FULFILLED,
    PROCESSING_RECEIVED,
    PROCESSING_ROUTING,
    PROCESSING_SHIPMENT_CREATED,
)
from logistics.models.shipment import Shipment

# Shopify-inspired customer-facing delivery labels
DELIVERY_STATUS_DISPLAY: dict[str, dict[str, str]] = {
    LOGISTICS_STATUS_PENDING: {"label": "Label created", "tone": "warning"},
    LOGISTICS_STATUS_PICKED_UP: {"label": "Picked up", "tone": "info"},
    LOGISTICS_STATUS_IN_TRANSIT: {"label": "In transit", "tone": "info"},
    LOGISTICS_STATUS_OUT_FOR_DELIVERY: {"label": "Out for delivery", "tone": "info"},
    LOGISTICS_STATUS_DELIVERED: {"label": "Delivered", "tone": "success"},
    LOGISTICS_STATUS_FAILED_DELIVERY: {"label": "Delivery failed", "tone": "critical"},
    LOGISTICS_STATUS_RETURNED: {"label": "Returned", "tone": "critical"},
}

# Internal fulfillment pipeline (Shopify admin-style)
PROCESSING_STATE_DISPLAY: dict[str, dict[str, Any]] = {
    PROCESSING_RECEIVED: {"label": "Awaiting fulfillment", "tone": "neutral", "step": 1},
    PROCESSING_ROUTING: {"label": "Preparing shipment", "tone": "info", "step": 2},
    PROCESSING_SHIPMENT_CREATED: {"label": "Ready to ship", "tone": "warning", "step": 3},
    PROCESSING_FULFILLED: {"label": "Fulfilled", "tone": "success", "step": 4},
    PROCESSING_FAILED: {"label": "Fulfillment failed", "tone": "critical", "step": 0},
}

PROCESSING_STATE_LABELS = {
    k: v["label"] for k, v in PROCESSING_STATE_DISPLAY.items()
}
DELIVERY_STATUS_LABELS = {k: v["label"] for k, v in DELIVERY_STATUS_DISPLAY.items()}

PROCESSING_TIMELINE_ORDER = (
    PROCESSING_RECEIVED,
    PROCESSING_ROUTING,
    PROCESSING_SHIPMENT_CREATED,
    PROCESSING_FULFILLED,
)

_BADGE_STYLES = {
    "neutral": ("#f5f5f4", "#57534e"),
    "info": ("#dbeafe", "#1d4ed8"),
    "warning": ("#ffedd5", "#b45309"),
    "success": ("#dcfce7", "#166534"),
    "critical": ("#fee2e2", "#b91c1c"),
}


@dataclass(frozen=True)
class ShipmentStatusView:
    headline: str
    subline: str
    headline_tone: str
    processing_label: str
    delivery_label: str
    processing_tone: str
    delivery_tone: str


def _meta(display_map: dict, key: str) -> dict[str, str]:
    return display_map.get(key, {"label": key.replace("_", " ").title(), "tone": "neutral"})


def delivery_status_label(status: str) -> str:
    return _meta(DELIVERY_STATUS_DISPLAY, status)["label"]


def processing_state_label(state: str) -> str:
    return _meta(PROCESSING_STATE_DISPLAY, state)["label"]


def shipment_status_view(shipment: Shipment) -> ShipmentStatusView:
    proc = _meta(PROCESSING_STATE_DISPLAY, shipment.processing_state)
    delivery = _meta(DELIVERY_STATUS_DISPLAY, shipment.shipment_status)

    if shipment.processing_state == PROCESSING_FAILED:
        return ShipmentStatusView(
            headline=proc["label"],
            subline=shipment.error_message[:120] if shipment.error_message else "Action required",
            headline_tone="critical",
            processing_label=proc["label"],
            delivery_label=delivery["label"],
            processing_tone=proc["tone"],
            delivery_tone=delivery["tone"],
        )

    if shipment.shipment_status == LOGISTICS_STATUS_DELIVERED:
        headline = delivery["label"]
        subline = proc["label"]
        tone = "success"
    elif shipment.shipment_status in (
        LOGISTICS_STATUS_IN_TRANSIT,
        LOGISTICS_STATUS_OUT_FOR_DELIVERY,
        LOGISTICS_STATUS_PICKED_UP,
    ):
        headline = delivery["label"]
        subline = f"Fulfillment · {proc['label']}"
        tone = delivery["tone"]
    elif shipment.processing_state == PROCESSING_FULFILLED:
        headline = proc["label"]
        subline = f"Delivery · {delivery['label']}"
        tone = proc["tone"]
    elif shipment.processing_state == PROCESSING_SHIPMENT_CREATED:
        headline = proc["label"]
        subline = f"Delivery · {delivery['label']}"
        tone = proc["tone"]
    else:
        headline = proc["label"]
        subline = "Fulfillment in progress"
        tone = proc["tone"]

    return ShipmentStatusView(
        headline=headline,
        subline=subline,
        headline_tone=tone,
        processing_label=proc["label"],
        delivery_label=delivery["label"],
        processing_tone=proc["tone"],
        delivery_tone=delivery["tone"],
    )


def processing_timeline(current_state: str) -> list[dict[str, Any]]:
    current_step = _meta(PROCESSING_STATE_DISPLAY, current_state).get("step", 0)
    if current_state == PROCESSING_FAILED:
        return []
    steps = []
    for key in PROCESSING_TIMELINE_ORDER:
        meta = PROCESSING_STATE_DISPLAY[key]
        step_num = meta["step"]
        steps.append(
            {
                "key": key,
                "label": meta["label"],
                "done": step_num < current_step,
                "current": key == current_state,
            }
        )
    return steps


def admin_status_badge(label: str, tone: str = "neutral") -> str:
    bg, fg = _BADGE_STYLES.get(tone, _BADGE_STYLES["neutral"])
    return format_html(
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        'font-size:11px;font-weight:600;letter-spacing:0.03em;background:{};color:{};">{}</span>',
        bg,
        fg,
        label,
    )
