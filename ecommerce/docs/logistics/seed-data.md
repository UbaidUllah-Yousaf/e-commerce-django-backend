# Logistics seed data

## Load fixture

From the `ecommerce/` directory (where `manage.py` lives):

```bash
DJANGO_USE_SQLITE=1 ./venv/bin/python manage.py seed_logistics
```

Or reload after clearing config:

```bash
DJANGO_USE_SQLITE=1 ./venv/bin/python manage.py seed_logistics --flush
```

Direct `loaddata` (same JSON):

```bash
DJANGO_USE_SQLITE=1 ./venv/bin/python manage.py loaddata logistics_sandbox
```

## What gets created

| Data | Details |
|------|---------|
| Couriers | TCS, Leopard, FallbackCo, Quiqup |
| City rules | Lahore → TCS; Karachi → Leopard; `*` → FallbackCo |
| Fulfillment config | Singleton pk=1, auto-fulfill on |
| Quiqup API key | On `Quiqup` courier `api_credentials.api_key` |
| Shopify demo | `demo-store.myshopify.com`, **inactive** — replace tokens in admin |

## Environment

See [`logistics/fixtures/env.sandbox.example`](../../logistics/fixtures/env.sandbox.example) for mock Quiqup URL and API key.

## Shopify webhook test payload

[`logistics/fixtures/sample_shopify_order.json`](../../logistics/fixtures/sample_shopify_order.json) — use with your store's webhook secret after enabling the demo store in admin.
