# Django admin setup

## Shopify stores

Add each store under **Logistics → Shopify stores**:

- `shop_domain` must match `X-Shopify-Shop-Domain` (e.g. `my-store.myshopify.com`)
- `access_token` — Admin API token
- `webhook_secret` — used for HMAC verification
- Toggle `is_active` to disable a store instantly

## City fulfillment rules

**Logistics → City fulfillment rules**

- Lower `priority` = higher precedence
- Use `*` as `city_name` for fallback
- `service_type` maps to Quiqup `service_kind`

## Couriers

**Logistics → Courier configurations**

- `courier_name` must match rule `courier_name`
- `supported_cities` — optional JSON list; empty = all cities

## Fulfillment configuration (singleton)

- `auto_fulfill_enabled` — create fulfillments after shipment
- `default_fallback_courier` — when no city rule matches
- `tracking_sync_enabled` — push tracking to platforms
- `ingest_api_token` — for custom order ingest API
