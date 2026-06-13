# Quiqup integration

Global credentials in environment (not Django admin):

- `QUIQUP_BASE_URL` — e.g. `https://platform-api.quiqup.com`
- `QUIQUP_CLIENT_ID`
- `QUIQUP_CLIENT_SECRET`

Shipments are created via `POST /api/fulfilment/orders` with `service_kind` from city rules.

## Tracking

- Webhook: `POST /api/v1/logistics/webhooks/quiqup/`
- Optional token: set `quiqup_webhook_secret` in Fulfillment configuration
- Polling: Celery beat runs `poll_quiqup_tracking_batch` every `LOGISTICS_QUIQUP_POLL_MINUTES` minutes
