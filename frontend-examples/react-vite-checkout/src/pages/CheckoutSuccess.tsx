import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { confirmOrderAfterStripe } from "../lib/checkoutApi";

/**
 * Route: /checkout/success?session_id=cs_test_...
 * Must match STOREFRONT_CHECKOUT_SUCCESS_PATH on the Django side.
 */
export function CheckoutSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [order, setOrder] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session_id in URL.");
      return;
    }
    confirmOrderAfterStripe(sessionId)
      .then(setOrder)
      .catch(() => setError("Payment received — order is still processing. Refresh in a moment."));
  }, [sessionId]);

  if (error) {
    return (
      <main style={{ padding: 24 }}>
        <h1>Checkout</h1>
        <p>{error}</p>
        <Link to="/">Home</Link>
      </main>
    );
  }

  if (!order) {
    return <main style={{ padding: 24 }}>Confirming your order…</main>;
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>Thank you!</h1>
      <p>
        Order <strong>{String(order.name)}</strong> — total {String(order.total)}{" "}
        {String(order.currency)}
      </p>
      <Link to="/">Continue shopping</Link>
    </main>
  );
}
