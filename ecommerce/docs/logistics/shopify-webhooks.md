# Shopify webhooks

Register per store in Shopify Admin → Settings → Notifications → Webhooks:

- **Event:** Order creation
- **URL:** `https://YOUR_DOMAIN/api/v1/logistics/webhooks/shopify/orders-create/`
- **Format:** JSON

The view identifies the store via `X-Shopify-Shop-Domain` and verifies HMAC with that store's `webhook_secret` from Django admin.

Inactive stores return HTTP 403.
