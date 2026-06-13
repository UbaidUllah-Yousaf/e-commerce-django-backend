# Celery workers

## Prerequisites

- Redis running (`REDIS_URL` in `.env`)
- Dependencies: `celery`, `redis`, `django-celery-beat`

## Commands

```bash
redis-server

celery -A settings worker -l info -Q logistics --concurrency=4

celery -A settings beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Main tasks

| Task | Purpose |
|------|---------|
| `process_shipment_pipeline` | Route → Quiqup → fulfill |
| `process_shopify_order_webhook` | Parse webhook log → pipeline |
| `process_custom_order` | New ecommerce order → pipeline |
| `sync_tracking_updates` | Status/tracking sync |
| `poll_quiqup_tracking_batch` | Scheduled polling (beat) |

Admin **Retry shipment** re-enqueues `process_shipment_pipeline`.
