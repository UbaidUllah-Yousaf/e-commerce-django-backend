import base64
import hashlib
import hmac
import json

from django.test import Client, TestCase

from logistics.models.shopify import ShopifyConfiguration
from logistics.models.shipment import WebhookLog


class ShopifyWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.shop = ShopifyConfiguration.objects.create(
            shop_name="Test",
            shop_domain="test.myshopify.com",
            access_token="token",
            webhook_secret="shhh_secret",
            is_active=True,
        )
        self.payload = {
            "id": 12345,
            "name": "#1001",
            "email": "a@b.com",
            "shipping_address": {"city": "Lahore", "first_name": "A", "last_name": "B"},
            "line_items": [{"title": "Item", "quantity": 1, "sku": "SKU1"}],
        }

    def _sign(self, body: bytes) -> str:
        digest = hmac.new(
            self.shop.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode()

    def test_valid_webhook_creates_log(self):
        body = json.dumps(self.payload).encode()
        r = self.client.post(
            "/api/v1/logistics/webhooks/shopify/orders-create/",
            data=body,
            content_type="application/json",
            HTTP_X_SHOPIFY_SHOP_DOMAIN="test.myshopify.com",
            HTTP_X_SHOPIFY_HMAC_SHA256=self._sign(body),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(WebhookLog.objects.count(), 1)

    def test_inactive_store_rejected(self):
        self.shop.is_active = False
        self.shop.save()
        body = json.dumps(self.payload).encode()
        r = self.client.post(
            "/api/v1/logistics/webhooks/shopify/orders-create/",
            data=body,
            content_type="application/json",
            HTTP_X_SHOPIFY_SHOP_DOMAIN="test.myshopify.com",
            HTTP_X_SHOPIFY_HMAC_SHA256=self._sign(body),
        )
        self.assertEqual(r.status_code, 403)

    def test_bad_hmac_rejected(self):
        body = json.dumps(self.payload).encode()
        r = self.client.post(
            "/api/v1/logistics/webhooks/shopify/orders-create/",
            data=body,
            content_type="application/json",
            HTTP_X_SHOPIFY_SHOP_DOMAIN="test.myshopify.com",
            HTTP_X_SHOPIFY_HMAC_SHA256="invalid",
        )
        self.assertEqual(r.status_code, 403)
