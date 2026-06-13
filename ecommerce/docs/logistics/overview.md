# Logistics overview

Centralized shipping pipeline:

1. Order ingested (Shopify webhook or ecommerce `Order` created)
2. Celery enqueues `process_shipment_pipeline`
3. City rules select courier + Quiqup `service_kind`
4. Quiqup shipment created
5. Auto-fulfillment on Shopify and/or `ecommerce.Fulfillment`
6. Tracking synced via Quiqup webhook or polling

All Shopify stores, city rules, and couriers are configured in **Django Admin → Logistics**.
