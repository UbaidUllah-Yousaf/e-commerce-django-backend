from rest_framework import serializers


class CheckoutRedirectUrlsSerializer(serializers.Serializer):
    """URLs to pass to Stripe (or omit on payment-session to use these)."""

    success_url = serializers.CharField()
    cancel_url = serializers.CharField()


class StripeStatusSerializer(serializers.Serializer):
    stripe_checkout_enabled = serializers.BooleanField()
    stripe_keys_configured = serializers.BooleanField()
    stripe_checkout_available = serializers.BooleanField()
    unavailable_reason = serializers.CharField(allow_blank=True)


class CheckoutPaymentOptionsSerializer(serializers.Serializer):
    stripe_checkout = serializers.BooleanField()
    stripe_checkout_available = serializers.BooleanField()
    stripe_keys_configured = serializers.BooleanField()
    stripe_unavailable_reason = serializers.CharField(allow_blank=True)
    cod = serializers.BooleanField()
    zero_total_complete = serializers.BooleanField()
    default_success_url = serializers.URLField(allow_blank=True, required=False)
    default_cancel_url = serializers.URLField(allow_blank=True, required=False)
    generated_checkout_urls = CheckoutRedirectUrlsSerializer()
    effective_checkout_urls = CheckoutRedirectUrlsSerializer()


class CreatePaymentSessionSerializer(serializers.Serializer):
    """
    URLs for Stripe Checkout redirect. Omit to use defaults from admin
    Checkout payment settings. success_url must include ``{CHECKOUT_SESSION_ID}``.
    """

    success_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="e.g. https://store.example/checkout/success?session_id={CHECKOUT_SESSION_ID}",
    )
    cancel_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="e.g. https://store.example/checkout/cancel",
    )


class PaymentSessionResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()
    session_id = serializers.CharField()
    publishable_key = serializers.CharField()


class StripeConfigSerializer(serializers.Serializer):
    """Public Stripe and checkout payment options for storefront initialization."""

    enabled = serializers.BooleanField()
    publishable_key = serializers.CharField(allow_blank=True)
    stripe = StripeStatusSerializer()
    payment_options = CheckoutPaymentOptionsSerializer()
