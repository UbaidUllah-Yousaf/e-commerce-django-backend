from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from logistics.mock.backend import create_mock_order, get_mock_order
from logistics.models.shipment import Shipment

logger = logging.getLogger("logistics.quiqup")

TOKEN_CACHE_KEY = "logistics:quiqup:access_token"


class QuiqupAPIError(Exception):
    pass


class QuiqupService:
    def __init__(self) -> None:
        self.use_mock = bool(getattr(settings, "QUIQUP_USE_MOCK", False))
        self.base_url = (getattr(settings, "QUIQUP_BASE_URL", "") or "").rstrip("/")
        self.client_id = getattr(settings, "QUIQUP_CLIENT_ID", "")
        self.client_secret = getattr(settings, "QUIQUP_CLIENT_SECRET", "")
        self.api_key = getattr(settings, "QUIQUP_API_KEY", "")

    def _get_token(self) -> str:
        if self.use_mock:
            return "mock-access-token"
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return cached
        if self.api_key:
            return self.api_key
        if not self.base_url or not self.client_id:
            raise QuiqupAPIError("Quiqup credentials not configured.")
        url = f"{self.base_url}/oauth/token"
        resp = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise QuiqupAPIError(f"Quiqup auth failed: {resp.status_code} {resp.text[:500]}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise QuiqupAPIError("Quiqup auth response missing access_token")
        expires_in = int(data.get("expires_in", 3600))
        cache.set(TOKEN_CACHE_KEY, token, timeout=max(expires_in - 60, 60))
        return token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_order_payload(self, shipment: Shipment) -> dict[str, Any]:
        addr = shipment.shipping_address or {}
        customer = shipment.customer_payload or {}
        items = []
        for line in shipment.line_items or []:
            items.append(
                {
                    "name": line.get("title") or line.get("name") or "Item",
                    "quantity": line.get("quantity", 1),
                    "sku": line.get("sku", ""),
                }
            )
        payload: dict[str, Any] = {
            "service_kind": shipment.service_type or "partner_next_day",
            "recipient": {
                "name": customer.get("name")
                or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                or "Customer",
                "phone": customer.get("phone") or addr.get("phone") or "",
                "email": customer.get("email") or "",
            },
            "delivery_address": {
                "address1": addr.get("address1") or addr.get("line1") or "",
                "address2": addr.get("address2") or addr.get("line2") or "",
                "city": shipment.city or addr.get("city") or "",
                "country": addr.get("country") or addr.get("country_code") or "",
                "postcode": addr.get("zip") or addr.get("postal_code") or "",
            },
            "items": items,
            "reference": shipment.idempotency_key,
        }
        if shipment.cod_amount and shipment.cod_amount > 0:
            payload["cod_amount"] = str(shipment.cod_amount)
        return payload

    def _apply_create_response(self, shipment: Shipment, body: dict[str, Any]) -> dict[str, Any]:
        order_data = body.get("order") or body
        shipment.quiqup_shipment_id = str(
            order_data.get("id") or order_data.get("order_id") or body.get("id") or ""
        )
        shipment.tracking_number = (
            order_data.get("tracking_number")
            or order_data.get("tracking_id")
            or body.get("tracking_number")
            or ""
        )
        shipment.tracking_url = order_data.get("tracking_url") or body.get("tracking_url") or ""
        shipment.response_payload = body
        shipment.save(
            update_fields=[
                "quiqup_shipment_id",
                "tracking_number",
                "tracking_url",
                "response_payload",
                "updated_at",
            ]
        )
        return body

    def create_shipment(self, shipment: Shipment) -> dict[str, Any]:
        if shipment.quiqup_shipment_id:
            return shipment.response_payload or {}
        payload = self._build_order_payload(shipment)
        shipment.request_payload = payload
        shipment.save(update_fields=["request_payload", "updated_at"])

        if self.use_mock:
            body = create_mock_order(payload)
            return self._apply_create_response(shipment, body)

        url = f"{self.base_url}/api/fulfilment/orders"
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=60)
        body: dict[str, Any] = {}
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:2000]}

        shipment.response_payload = body
        if resp.status_code >= 400:
            shipment.error_message = f"Quiqup error {resp.status_code}: {resp.text[:500]}"
            shipment.save(update_fields=["response_payload", "error_message", "updated_at"])
            raise QuiqupAPIError(shipment.error_message)

        return self._apply_create_response(shipment, body)

    def get_tracking_status(self, quiqup_shipment_id: str) -> dict[str, Any]:
        if self.use_mock:
            try:
                return get_mock_order(quiqup_shipment_id)
            except KeyError as exc:
                raise QuiqupAPIError(f"Mock order not found: {quiqup_shipment_id}") from exc

        url = f"{self.base_url}/api/fulfilment/orders/{quiqup_shipment_id}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise QuiqupAPIError(f"Quiqup tracking failed: {resp.status_code}")
        return resp.json()
