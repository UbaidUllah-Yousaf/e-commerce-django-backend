"""
Fulfillment-related choices.

* ``FULFILLMENT_STATUS_*`` — aggregate status on Order / OrderLineItem (Shopify ``fulfillment_status``).
* ``SHIPMENT_STATUS_*`` — per-package ``Fulfillment`` row status (shipment lifecycle).
"""

# --- Order / line aggregate (Shopify fulfillment_status) ---------------------------------

FULFILLMENT_STATUS_UNFULFILLED = "unfulfilled"
FULFILLMENT_STATUS_PARTIAL = "partial"
FULFILLMENT_STATUS_FULFILLED = "fulfilled"
FULFILLMENT_STATUS_CHOICES = (
    (FULFILLMENT_STATUS_UNFULFILLED, "Unfulfilled"),
    (FULFILLMENT_STATUS_PARTIAL, "Partial"),
    (FULFILLMENT_STATUS_FULFILLED, "Fulfilled"),
)

# --- Per-shipment Fulfillment model (package / shipment status) -------------------------

SHIPMENT_STATUS_PENDING = "pending"
SHIPMENT_STATUS_OPEN = "open"
SHIPMENT_STATUS_IN_TRANSIT = "in_transit"
SHIPMENT_STATUS_SUCCESS = "success"
SHIPMENT_STATUS_CANCELLED = "cancelled"
SHIPMENT_STATUS_ERROR = "error"
SHIPMENT_STATUS_FAILURE = "failure"

SHIPMENT_STATUS_CHOICES = (
    (SHIPMENT_STATUS_PENDING, "Pending"),
    (SHIPMENT_STATUS_OPEN, "Open"),
    (SHIPMENT_STATUS_IN_TRANSIT, "In transit"),
    (SHIPMENT_STATUS_SUCCESS, "Fulfilled"),
    (SHIPMENT_STATUS_CANCELLED, "Cancelled"),
    (SHIPMENT_STATUS_ERROR, "Error"),
    (SHIPMENT_STATUS_FAILURE, "Failure"),
)

SHIPMENT_STATUS_LABELS = dict(SHIPMENT_STATUS_CHOICES)

SHIPMENT_TERMINAL_VOID_STATUSES = frozenset(
    {SHIPMENT_STATUS_CANCELLED, SHIPMENT_STATUS_ERROR, SHIPMENT_STATUS_FAILURE}
)

# --- API: create order fulfillment (POST body ``scope``) --------------------------------

FULFILLMENT_CREATE_SCOPE_COMPLETE = "complete"
FULFILLMENT_CREATE_SCOPE_PARTIAL = "partial"
FULFILLMENT_CREATE_SCOPE_CHOICES = (
    (FULFILLMENT_CREATE_SCOPE_COMPLETE, "Complete remaining"),
    (FULFILLMENT_CREATE_SCOPE_PARTIAL, "Partial lines"),
)
