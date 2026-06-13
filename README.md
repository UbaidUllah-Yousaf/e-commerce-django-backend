# E-commerce Django Backend

Django REST API for a Shopify-style storefront: catalog, checkout, orders, Stripe payments, and a logistics pipeline (Shopify webhooks, Quiqup courier, Celery workers).

**Repository:** [UbaidUllah-Yousaf/e-commerce-django-backend](https://github.com/UbaidUllah-Yousaf/e-commerce-django-backend)

## Features

- **Storefront API** — products, variants, collections, tags, checkouts, orders, discount codes, gift cards, customer profiles
- **Payments** — Stripe Checkout sessions and webhooks; COD support via checkout payment settings
- **Auth** — JWT via `dj-rest-auth` / SimpleJWT and `django-allauth`
- **Logistics** — centralized shipping: city-based courier routing, Quiqup shipments, Shopify-style fulfillments, tracking sync
- **Admin** — Django Admin with Unfold UI; import/export for catalog data
- **API docs** — OpenAPI schema and Swagger UI at `/api/docs/`

## Project layout

```
ecommerce-django/
├── ecommerce/                 # Django project (run commands from here)
│   ├── manage.py
│   ├── settings/
│   ├── ecommerce/             # Storefront app (models, API, Stripe)
│   ├── logistics/             # Shipping & fulfillment app
│   ├── docs/                  # Detailed integration guides
│   └── docker-compose.yml     # PostgreSQL for local dev
├── frontend-examples/
│   └── react-vite-checkout/   # Example React checkout redirect pages
└── requirements.txt           # Minimal deps; use ecommerce/requirements.txt for full install
```

## Requirements

- Python 3.11+
- PostgreSQL 16 (or SQLite for tests via `DJANGO_USE_SQLITE=1`)
- Redis (Celery broker, required for logistics background tasks)

## Quick start

### 1. Clone and enter the Django project

```bash
git clone https://github.com/UbaidUllah-Yousaf/e-commerce-django-backend.git
cd e-commerce-django-backend/ecommerce
```

### 2. Virtual environment and dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
```

Edit `.env` for PostgreSQL, Redis, Stripe keys, and optional storefront redirect URLs. See [ecommerce/docs/logistics/env-reference.md](ecommerce/docs/logistics/env-reference.md) for logistics-related variables.

### 4. Start PostgreSQL

```bash
docker compose up -d
```

Defaults match `.env.example`: database `ecommerce`, user/password `ecommerce`, port `5432`.

### 5. Migrate and run

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/admin/ | Django Admin |
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/api/v1/ | REST API root |

### 6. Optional: Celery (logistics)

In separate terminals, with Redis running (`REDIS_URL` in `.env`, default `redis://localhost:6379/0`):

```bash
celery -A settings worker -l info -Q logistics
celery -A settings beat -l info
```

## Seed data

```bash
# Sample catalog / collections
python manage.py dummy_data
python manage.py seed_shopify_collections

# Logistics sandbox config (mock Quiqup)
python manage.py seed_logistics
```

Import products from Shopify CSV:

```bash
python manage.py import_shopify_products path/to/export.csv
```

## API overview

Base path: `/api/v1/`

| Area | Examples |
|------|----------|
| Catalog | `GET /products/`, `GET /collections/`, `GET /variants/` |
| Checkout | `POST /checkouts/`, `POST /checkouts/{id}/payment-session/` |
| Orders | `GET /orders/`, `POST /orders/{id}/fulfillments/` |
| Stripe | `GET /stripe/config/`, `POST /stripe/webhook/` |
| Auth | `POST /auth/login/`, `POST /auth/registration/` |
| Logistics | `/api/v1/logistics/` (webhooks, ingest, mock Quiqup) |

Interactive docs: `/api/docs/`.

## Frontend integration

Example React + Vite checkout pages live in `frontend-examples/react-vite-checkout/`. Configure storefront redirect URLs in `.env`:

```env
STOREFRONT_BASE_URL=http://localhost:5173
STOREFRONT_CHECKOUT_SUCCESS_PATH=/checkout/success
STOREFRONT_CHECKOUT_CANCEL_PATH=/checkout/cancel
```

See [frontend-examples/react-vite-checkout/README.md](frontend-examples/react-vite-checkout/README.md).

## Documentation

| Guide | Path |
|-------|------|
| Docs index | [ecommerce/docs/README.md](ecommerce/docs/README.md) |
| Logistics overview | [ecommerce/docs/logistics/overview.md](ecommerce/docs/logistics/overview.md) |
| Django admin (logistics) | [ecommerce/docs/logistics/django-admin-setup.md](ecommerce/docs/logistics/django-admin-setup.md) |
| Celery workers | [ecommerce/docs/logistics/celery-workers.md](ecommerce/docs/logistics/celery-workers.md) |
| Quiqup integration | [ecommerce/docs/logistics/quiqup-integration.md](ecommerce/docs/logistics/quiqup-integration.md) |
| Logistics app README | [ecommerce/logistics/README.md](ecommerce/logistics/README.md) |

## Testing

Use SQLite without PostgreSQL:

```bash
DJANGO_USE_SQLITE=1 python manage.py test
```

## Tech stack

Django 6, Django REST Framework, PostgreSQL, Celery, Redis, Stripe, Cloudinary, drf-spectacular, django-unfold, django-import-export.
