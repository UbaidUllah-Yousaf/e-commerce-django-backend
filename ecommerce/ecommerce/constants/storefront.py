"""
Default React + Vite storefront paths for Stripe Checkout redirects.

Override via STOREFRONT_CHECKOUT_SUCCESS_PATH / STOREFRONT_CHECKOUT_CANCEL_PATH in .env.
"""

STOREFRONT_CHECKOUT_SUCCESS_PATH = "/checkout/success"
STOREFRONT_CHECKOUT_CANCEL_PATH = "/checkout/cancel"

# Query param read on the success page after Stripe redirect (Stripe replaces the placeholder).
STRIPE_SESSION_QUERY_PARAM = "session_id"
