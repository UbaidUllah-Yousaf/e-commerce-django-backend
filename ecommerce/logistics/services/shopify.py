from __future__ import annotations

import logging
from typing import Any

import requests

from logistics.constants import SOURCE_PLATFORM_SHOPIFY
from logistics.models.shopify import ShopifyConfiguration

logger = logging.getLogger("logistics.shopify")


class ShopifyAPIError(Exception):
    pass


class ShopifyService:
    def __init__(self, shop: ShopifyConfiguration) -> None:
        self.shop = shop
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": shop.access_token,
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.shop.admin_api_base_url}/{path.lstrip('/')}"
        resp = self.session.request(method, url, timeout=60, **kwargs)
        if resp.status_code == 429:
            raise ShopifyAPIError("Shopify rate limited (429)")
        if resp.status_code >= 400:
            raise ShopifyAPIError(f"Shopify API {resp.status_code}: {resp.text[:500]}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def create_fulfillment(
        self,
        order_id: str,
        *,
        tracking_number: str = "",
        tracking_company: str = "",
        tracking_url: str = "",
        notify_customer: bool = True,
    ) -> dict[str, Any]:
        fo_resp = self._request(
            "GET",
            f"orders/{order_id}/fulfillment_orders.json",
        )
        fulfillment_orders = fo_resp.get("fulfillment_orders") or []
        open_orders = [
            fo
            for fo in fulfillment_orders
            if fo.get("status") in ("open", "in_progress", "scheduled")
        ]
        if not open_orders:
            raise ShopifyAPIError(f"No open fulfillment orders for Shopify order {order_id}")

        line_items_by_fo = []
        for fo in open_orders:
            line_items_by_fo.append(
                {
                    "fulfillment_order_id": fo["id"],
                    "fulfillment_order_line_items": [
                        {"id": li["id"], "quantity": li.get("quantity", 1)}
                        for li in fo.get("line_items", [])
                    ],
                }
            )

        payload: dict[str, Any] = {
            "fulfillment": {
                "notify_customer": notify_customer,
                "line_items_by_fulfillment_order": line_items_by_fo,
            }
        }
        tracking_info: dict[str, str] = {}
        if tracking_number:
            tracking_info["number"] = tracking_number
        if tracking_company:
            tracking_info["company"] = tracking_company
        if tracking_url:
            tracking_info["url"] = tracking_url
        if tracking_info:
            payload["fulfillment"]["tracking_info"] = tracking_info

        return self._request("POST", "fulfillments.json", json=payload)

    def update_fulfillment_tracking(
        self,
        fulfillment_id: str,
        *,
        tracking_number: str,
        tracking_company: str = "",
        tracking_url: str = "",
    ) -> dict[str, Any]:
        payload = {
            "fulfillment": {
                "notify_customer": True,
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                    "url": tracking_url,
                },
            }
        }
        return self._request(
            "POST",
            f"fulfillments/{fulfillment_id}/update_tracking.json",
            json=payload,
        )
