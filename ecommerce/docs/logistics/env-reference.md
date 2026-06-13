# Logistics environment variables

Add to `ecommerce/.env`:

```env
REDIS_URL=redis://localhost:6379/0
QUIQUP_BASE_URL=https://platform-api.staging.quiqup.com
QUIQUP_CLIENT_ID=
QUIQUP_CLIENT_SECRET=
LOGISTICS_QUIQUP_POLL_MINUTES=15
```

Shopify credentials are **not** in env — configure stores in Django admin.
