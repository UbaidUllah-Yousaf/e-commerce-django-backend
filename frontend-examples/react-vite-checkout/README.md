# React + Vite — Stripe checkout redirect URLs

Django generates default success/cancel URLs for your Vite dev server:

| Page | Path | Query |
|------|------|--------|
| Success | `/checkout/success` | `?session_id={CHECKOUT_SESSION_ID}` (set by Stripe) |
| Cancel | `/checkout/cancel` | — |

Configured via `ecommerce/.env`:

```env
STOREFRONT_BASE_URL=http://localhost:5173
STOREFRONT_CHECKOUT_SUCCESS_PATH=/checkout/success
STOREFRONT_CHECKOUT_CANCEL_PATH=/checkout/cancel
```

## React Router

```tsx
import { CheckoutSuccess } from "./pages/CheckoutSuccess";
import { CheckoutCancel } from "./pages/CheckoutCancel";

{ path: "/checkout/success", element: <CheckoutSuccess /> },
{ path: "/checkout/cancel", element: <CheckoutCancel /> },
```

## Pay button

```tsx
import { startStripeCheckout } from "./lib/checkoutApi";

<button type="button" onClick={() => startStripeCheckout(checkoutId)}>
  Pay with card
</button>
```

`startStripeCheckout` loads `GET /api/v1/stripe/config/` and uses `payment_options.effective_checkout_urls` — no need to hardcode URLs in the frontend.

## Optional: empty payment-session body

If admin defaults are set (auto-filled from env), you can POST without a body:

```http
POST /api/v1/checkouts/{id}/payment-session/
{}
```
