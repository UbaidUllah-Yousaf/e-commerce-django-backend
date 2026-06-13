from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.constants.checkout import (
    CHECKOUT_STATUS_OPEN,
    ORDER_FINANCIAL_PAID,
    ORDER_FINANCIAL_PENDING,
)
from ecommerce.filters import CheckoutFilter, CheckoutLineItemFilter, OrderFilter
from ecommerce.models.checkout import (
    Checkout,
    CheckoutGiftCardApplication,
    CheckoutLineItem,
    Order,
)
from ecommerce.models.discount import DiscountCode
from ecommerce.models.fulfillment import Fulfillment, fulfillment_remaining_lines
from ecommerce.models.gift_card import GiftCard
from ecommerce.serializers.fulfillment import (
    CreateOrderFulfillmentSerializer,
    FulfillmentSerializer,
)
from ecommerce.serializers.checkout import (
    ApplyDiscountSerializer,
    ApplyGiftCardSerializer,
    CheckoutLineItemSerializer,
    CheckoutSerializer,
    OrderSerializer,
    RemoveGiftCardSerializer,
)
from ecommerce.serializers.stripe import CreatePaymentSessionSerializer
from ecommerce.services import checkout_pricing
from ecommerce.services.fulfillment_ops import FulfillmentCreateError, create_order_fulfillment
from ecommerce.services.checkout_payment_settings import (
    cod_complete_allowed,
    payment_required_for_checkout,
    resolve_checkout_redirect_urls,
    stripe_unavailable_reason,
)
from ecommerce.services.stripe_checkout import (
    StripeCheckoutError,
    checkout_amount_due,
    create_checkout_payment_session,
)


class CheckoutViewSet(viewsets.ModelViewSet):
    """
    Shopify-style checkout session: addresses, shipping/tax, line items,
    discount codes, gift cards, and completion into an order.
    """

    queryset = Checkout.objects.all().prefetch_related(
        "line_items__variant__product",
        "gift_card_applications__gift_card",
    ).select_related("discount_code")
    serializer_class = CheckoutSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options", "patch"]
    filterset_class = CheckoutFilter
    ordering_fields = ("created_at", "updated_at", "status", "email", "currency", "id")

    def perform_update(self, serializer):
        if serializer.instance.status != CHECKOUT_STATUS_OPEN:
            raise ValidationError("Only open checkouts can be updated.")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="apply-discount")
    def apply_discount(self, request, pk=None):
        checkout = self.get_object()
        if checkout.status != CHECKOUT_STATUS_OPEN:
            return Response(
                {"detail": "Checkout is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = ApplyDiscountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code_value = ser.validated_data["code"]
        code = DiscountCode.objects.filter(code__iexact=code_value).first()
        if not code:
            return Response(
                {"detail": "Discount code not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        subtotal = checkout_pricing.line_items_subtotal(checkout)
        err = checkout_pricing.validate_discount_for_apply(code, subtotal)
        if err:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        checkout.discount_code = code
        checkout.save(update_fields=["discount_code", "updated_at"])
        checkout_pricing.recalculate_checkout(checkout)
        checkout.refresh_from_db()
        return Response(CheckoutSerializer(checkout).data)

    @action(detail=True, methods=["post"], url_path="remove-discount")
    def remove_discount(self, request, pk=None):
        checkout = self.get_object()
        if checkout.status != CHECKOUT_STATUS_OPEN:
            return Response(
                {"detail": "Checkout is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        checkout.discount_code = None
        checkout.discount_amount = Decimal("0.00")
        checkout.save(update_fields=["discount_code", "discount_amount", "updated_at"])
        checkout_pricing.recalculate_checkout(checkout)
        checkout.refresh_from_db()
        return Response(CheckoutSerializer(checkout).data)

    @action(detail=True, methods=["post"], url_path="apply-gift-card")
    def apply_gift_card(self, request, pk=None):
        checkout = self.get_object()
        if checkout.status != CHECKOUT_STATUS_OPEN:
            return Response(
                {"detail": "Checkout is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = ApplyGiftCardSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code_value = ser.validated_data["code"].strip().upper()
        gift_card = GiftCard.objects.filter(code=code_value).first()
        if not gift_card:
            return Response(
                {"detail": "Gift card not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        err = checkout_pricing.validate_gift_card_for_apply(gift_card)
        if err:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)

        if checkout.gift_card_applications.filter(gift_card=gift_card).exists():
            return Response(
                {"detail": "This gift card is already applied to the checkout."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkout_pricing.recalculate_checkout(checkout)
        discount_amt = checkout_pricing.compute_discount_amount(
            checkout_pricing.line_items_subtotal(checkout),
            checkout.discount_code,
        )
        due = checkout_pricing.amount_due_before_gift_cards(checkout, discount_amt)
        other = (
            checkout.gift_card_applications.aggregate(s=Sum("amount_applied"))["s"]
            or Decimal("0.00")
        )
        remaining = checkout_pricing.quantize_money(due - other)
        if remaining <= Decimal("0.00"):
            return Response(
                {"detail": "No remaining balance to apply a gift card to."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        applied = checkout_pricing.quantize_money(
            min(gift_card.current_balance, remaining)
        )
        CheckoutGiftCardApplication.objects.create(
            checkout=checkout,
            gift_card=gift_card,
            amount_applied=applied,
        )
        checkout_pricing.recalculate_checkout(checkout)
        checkout.refresh_from_db()
        return Response(CheckoutSerializer(checkout).data)

    @action(detail=True, methods=["post"], url_path="remove-gift-card")
    def remove_gift_card(self, request, pk=None):
        checkout = self.get_object()
        if checkout.status != CHECKOUT_STATUS_OPEN:
            return Response(
                {"detail": "Checkout is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = RemoveGiftCardSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        qs = checkout.gift_card_applications.all()
        gift_card_id = ser.validated_data.get("gift_card_id")
        code = ser.validated_data.get("code")
        if gift_card_id:
            qs = qs.filter(gift_card_id=gift_card_id)
        elif code:
            qs = qs.filter(gift_card__code=code.strip().upper())
        deleted, _ = qs.delete()
        if not deleted:
            return Response(
                {"detail": "No matching gift card application on this checkout."},
                status=status.HTTP_404_NOT_FOUND,
            )
        checkout_pricing.recalculate_checkout(checkout)
        checkout.refresh_from_db()
        return Response(CheckoutSerializer(checkout).data)

    @action(detail=True, methods=["post"], url_path="payment-session")
    def payment_session(self, request, pk=None):
        """
        Create a Stripe Checkout Session and return the hosted payment URL.

        Requires checkout email, line items, and amount due > 0.
        """
        checkout = self.get_object()
        if checkout.status != CHECKOUT_STATUS_OPEN:
            return Response(
                {"detail": "Checkout is not open."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = CreatePaymentSessionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        customer_id = request.user.pk if request.user.is_authenticated else None
        try:
            success_url, cancel_url = resolve_checkout_redirect_urls(
                ser.validated_data.get("success_url"),
                ser.validated_data.get("cancel_url"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = create_checkout_payment_session(
                checkout,
                success_url=success_url,
                cancel_url=cancel_url,
                customer_user_id=customer_id,
            )
        except StripeCheckoutError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        with transaction.atomic():
            checkout = (
                Checkout.objects.select_for_update(of=("self",))
                .prefetch_related(
                    "line_items__variant__product",
                    "gift_card_applications__gift_card",
                )
                .select_related("discount_code")
                .get(pk=pk)
            )
            if checkout.status != CHECKOUT_STATUS_OPEN:
                raise ValidationError("Checkout is not open.")

            due = checkout_amount_due(checkout)
            if payment_required_for_checkout(due):
                detail = (
                    "Payment is required. Create a payment session via "
                    "POST /api/v1/checkouts/{id}/payment-session/ and "
                    "complete payment in Stripe, or enable Cash on Delivery (COD) "
                    "in Checkout payment settings."
                )
                reason = stripe_unavailable_reason()
                if reason:
                    detail = f"{detail} {reason}"
                raise ValidationError(
                    {"detail": detail, "code": "payment_required"},
                )

            financial_status = ORDER_FINANCIAL_PAID
            if due > Decimal("0.00") and cod_complete_allowed():
                financial_status = ORDER_FINANCIAL_PENDING

            try:
                customer = request.user if request.user.is_authenticated else None
                order = checkout_pricing.complete_checkout(
                    checkout,
                    customer=customer,
                    financial_status=financial_status,
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        order = (
            order.__class__.objects.prefetch_related("line_items__variant")
            .select_related("checkout")
            .get(pk=order.pk)
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CheckoutLineItemViewSet(viewsets.ModelViewSet):
    queryset = CheckoutLineItem.objects.select_related(
        "checkout",
        "variant__product",
    ).all()
    serializer_class = CheckoutLineItemSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "head", "options", "patch", "delete"]
    filterset_class = CheckoutLineItemFilter
    ordering_fields = ("id", "created_at", "updated_at", "quantity")

    def get_queryset(self):
        qs = super().get_queryset()
        checkout_id = self.request.query_params.get("checkout")
        if checkout_id is not None:
            qs = qs.filter(checkout_id=checkout_id)
        return qs

    def perform_destroy(self, instance):
        checkout = instance.checkout
        if checkout.status != CHECKOUT_STATUS_OPEN:
            raise ValidationError("Cannot modify line items on a closed checkout.")
        super().perform_destroy(instance)
        checkout_pricing.recalculate_checkout(checkout)

    def perform_create(self, serializer):
        checkout = serializer.validated_data["checkout"]
        if checkout.status != CHECKOUT_STATUS_OPEN:
            raise ValidationError("Cannot add line items to a closed checkout.")
        serializer.save()

    def perform_update(self, serializer):
        checkout = serializer.instance.checkout
        if checkout.status != CHECKOUT_STATUS_OPEN:
            raise ValidationError("Cannot update line items on a closed checkout.")
        serializer.save()


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.prefetch_related(
        "line_items__variant",
        "fulfillments__fulfillment_service",
        "fulfillments__line_items__order_line_item",
    ).select_related(
        "checkout",
        "customer",
    ).all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    ordering_fields = (
        "created_at",
        "updated_at",
        "total",
        "subtotal",
        "financial_status",
        "currency",
        "id",
        "order_number",
        "name",
    )

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        ownership = Q(customer_id=user.pk)
        if user.email:
            ownership |= Q(email__iexact=user.email.strip())
        return qs.filter(ownership)

    @action(
        detail=True,
        methods=["get"],
        url_path="fulfillment-inventory",
        permission_classes=[IsAdminUser],
    )
    def fulfillment_inventory(self, request, pk=None):
        """
        Remaining quantities per order line (Shopify-style fulfillable / delivered snapshot).
        """
        order = self.get_object()
        return Response(fulfillment_remaining_lines(order))

    @action(
        detail=True,
        methods=["post"],
        url_path="fulfillments",
        permission_classes=[IsAdminUser],
    )
    def create_fulfillment(self, request, pk=None):
        """
        Create a fulfillment for this order.

        * ``scope``: ``complete`` (all remaining units) or ``partial`` (explicit ``line_items``).
        * ``manual``: ``true`` for manual fulfillment (no ``fulfillment_service``); optional tracking.
        * ``fulfillment_service``: optional carrier profile when ``manual`` is false.
        * Default ``status`` is ``success`` (mark fulfilled); use ``pending`` / ``in_transit`` for carrier flows.
        """
        order = self.get_object()
        ser = CreateOrderFulfillmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        line_items = data.pop("line_items", None)
        fulfillment_service = data.pop("fulfillment_service", None)
        if line_items is not None:
            line_items = [
                {"order_line_item": row["order_line_item"], "quantity": row["quantity"]}
                for row in line_items
            ]
        try:
            fulfillment = create_order_fulfillment(
                order,
                fulfillment_service=fulfillment_service,
                line_items=line_items,
                **data,
            )
        except FulfillmentCreateError as exc:
            raise ValidationError(str(exc)) from exc
        fulfillment = (
            Fulfillment.objects.prefetch_related("line_items__order_line_item")
            .select_related("fulfillment_service")
            .get(pk=fulfillment.pk)
        )
        return Response(
            FulfillmentSerializer(fulfillment).data,
            status=status.HTTP_201_CREATED,
        )
