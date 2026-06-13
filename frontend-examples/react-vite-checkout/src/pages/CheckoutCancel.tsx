import { Link } from "react-router-dom";

/** Route: /checkout/cancel — matches STOREFRONT_CHECKOUT_CANCEL_PATH */
export function CheckoutCancel() {
  return (
    <main style={{ padding: 24 }}>
      <h1>Payment cancelled</h1>
      <p>Your cart is still saved. You can try checkout again when you are ready.</p>
      <Link to="/cart">Back to cart</Link>
    </main>
  );
}
