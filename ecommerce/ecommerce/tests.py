from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from ecommerce.constants.checkout import CHECKOUT_STATUS_COMPLETED
from ecommerce.constants.discount import DISCOUNT_TYPE_PERCENTAGE
from ecommerce.constants.fulfillment import (
    FULFILLMENT_CREATE_SCOPE_COMPLETE,
    FULFILLMENT_CREATE_SCOPE_PARTIAL,
    FULFILLMENT_STATUS_FULFILLED,
    FULFILLMENT_STATUS_PARTIAL,
    FULFILLMENT_STATUS_UNFULFILLED,
    SHIPMENT_STATUS_CANCELLED,
    SHIPMENT_STATUS_PENDING,
    SHIPMENT_STATUS_SUCCESS,
)
from ecommerce.models.checkout import Checkout, Order
from ecommerce.models.collection import Collection
from ecommerce.models.discount import DiscountCode
from ecommerce.models.fulfillment import (
    Fulfillment,
    FulfillmentLineItem,
    FulfillmentService,
    get_order_fulfillment_state,
    get_order_line_fulfillment_state,
)
from ecommerce.models.gift_card import GiftCard
from ecommerce.models.product import Product, ProductVariant
from ecommerce.models.size_chart import (
    SizeChart,
    SizeChartCell,
    SizeChartColumn,
    SizeChartRow,
)
from ecommerce.models.checkout_payment import CheckoutPaymentSettings
from ecommerce.models.tag import Tag
from ecommerce.services.size_chart_grid import (
    apply_grid_payload_to_chart,
    chart_to_grid_dict,
    validate_grid_payload,
)


class CheckoutApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.collection = Collection.objects.create(title="Test", is_active=True)
        self.product = Product.objects.create(
            title="Widget",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title="Default",
            sku="W-1",
            price=Decimal("20.00"),
            inventory_quantity=5,
            is_active=True,
        )
        self.discount = DiscountCode.objects.create(
            code="SAVE10",
            discount_type=DISCOUNT_TYPE_PERCENTAGE,
            value=Decimal("10"),
            minimum_subtotal=Decimal("0"),
            is_active=True,
        )
        self.gift = GiftCard.objects.create(
            code="GIFT500",
            initial_balance=Decimal("50.00"),
            current_balance=Decimal("50.00"),
            is_active=True,
        )

    def test_apply_discount_accepts_coupon_code_alias(self):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        checkout_id = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": checkout_id, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        r = self.client.post(
            f"/api/v1/checkouts/{checkout_id}/apply-discount/",
            {"coupon_code": "SAVE10"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["discount_code_string"], "SAVE10")

    def test_apply_discount_case_insensitive_lookup(self):
        dc = DiscountCode.objects.create(
            code="SummerSale",
            discount_type=DISCOUNT_TYPE_PERCENTAGE,
            value=Decimal("5"),
            minimum_subtotal=Decimal("0"),
            is_active=True,
        )
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        checkout_id = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": checkout_id, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        r = self.client.post(
            f"/api/v1/checkouts/{checkout_id}/apply-discount/",
            {"code": "summersale"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["discount_code_string"], "SummerSale")
        dc.delete()

    def test_checkout_flow_with_discount_and_gift_card(self):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        checkout_id = r.data["id"]

        r = self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": checkout_id, "variant": self.variant.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

        r = self.client.post(
            f"/api/v1/checkouts/{checkout_id}/apply-discount/",
            {"code": "save10"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["discount_code_string"], "SAVE10")

        r = self.client.post(
            f"/api/v1/checkouts/{checkout_id}/apply-gift-card/",
            {"code": "gift500"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data["gift_card_applications"]), 1)

        r = self.client.post(f"/api/v1/checkouts/{checkout_id}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["total"], "0.00")

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.inventory_quantity, 3)

        self.gift.refresh_from_db()
        self.assertEqual(self.gift.current_balance, Decimal("14.00"))

        self.discount.refresh_from_db()
        self.assertEqual(self.discount.usage_count, 1)

        checkout = Checkout.objects.get(pk=checkout_id)
        self.assertEqual(checkout.status, CHECKOUT_STATUS_COMPLETED)

    def test_remove_discount_and_gift_card(self):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        cid = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        self.client.post(f"/api/v1/checkouts/{cid}/apply-discount/", {"code": "SAVE10"}, format="json")
        self.client.post(f"/api/v1/checkouts/{cid}/apply-gift-card/", {"code": "GIFT500"}, format="json")
        self.client.post(f"/api/v1/checkouts/{cid}/remove-discount/", {}, format="json")
        r = self.client.get(f"/api/v1/checkouts/{cid}/")
        self.assertIsNone(r.data["discount_code"])
        self.client.post(
            f"/api/v1/checkouts/{cid}/remove-gift-card/",
            {"code": "GIFT500"},
            format="json",
        )
        r = self.client.get(f"/api/v1/checkouts/{cid}/")
        self.assertEqual(len(r.data["gift_card_applications"]), 0)


class CustomerDetailsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _auth_headers(self):
        r = self.client.post(
            '/api/v1/auth/registration/',
            {
                'email': 'buyer@example.com',
                'password1': 'SecurePass1!',
                'password2': 'SecurePass1!',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        token = r.data['access']
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_customer_me_and_addresses(self):
        h = self._auth_headers()
        r = self.client.get('/api/v1/customers/me/', **h)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['email'], 'buyer@example.com')
        self.assertEqual(r.data['addresses'], [])

        r = self.client.patch(
            '/api/v1/customers/me/',
            {
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'phone': '+15551234567',
                'accepts_marketing': True,
            },
            format='json',
            **h,
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['first_name'], 'Ada')
        self.assertTrue(r.data['accepts_marketing'])

        r = self.client.post(
            '/api/v1/customers/me/addresses/',
            {
                'address1': '123 Main St',
                'city': 'San Francisco',
                'province_code': 'CA',
                'country_code': 'us',
                'zip': '94102',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'is_default_shipping': True,
                'is_default_billing': True,
            },
            format='json',
            **h,
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['country_code'], 'US')

        r = self.client.get('/api/v1/customers/me/', **h)
        self.assertEqual(len(r.data['addresses']), 1)
        self.assertEqual(r.data['addresses'][0]['city'], 'San Francisco')


class AuthJwtTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login_return_jwt(self):
        r = self.client.post(
            '/api/v1/auth/registration/',
            {
                'email': 'merchant@example.com',
                'password1': 'ShopifyStyle9!',
                'password2': 'ShopifyStyle9!',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertIn('access', r.data)
        self.assertIn('refresh', r.data)
        self.assertIn('user', r.data)

        r2 = self.client.post(
            '/api/v1/auth/login/',
            {
                'email': 'merchant@example.com',
                'password': 'ShopifyStyle9!',
            },
            format='json',
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.content)
        self.assertIn('access', r2.data)
        token = r2.data['access']
        r3 = self.client.get(
            '/api/v1/auth/user/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json',
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertEqual(r3.data['email'], 'merchant@example.com')


class OrderApiAuthorizationTests(TestCase):
    """Orders list/detail must not leak across customers."""

    def setUp(self):
        self.client = APIClient()
        self.collection = Collection.objects.create(title="O", is_active=True)
        self.product = Product.objects.create(
            title="P",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title="V",
            sku="SKU-O",
            price=Decimal("10.00"),
            inventory_quantity=10,
            is_active=True,
        )

    def _register_and_headers(self, email: str, password: str) -> dict:
        r = self.client.post(
            "/api/v1/auth/registration/",
            {
                "email": email,
                "password1": password,
                "password2": password,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        token = r.data["access"]
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_orders_list_requires_authentication(self):
        r = self.client.get("/api/v1/orders/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_cannot_read_other_users_order(self):
        h_a = self._register_and_headers("alice@orders.test", "Zebra-Hill-9-Quartz!")
        h_b = self._register_and_headers("bob@orders.test", "Mango-River-4-Cobalt!")

        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        cid = r.data["id"]
        self.client.patch(
            f"/api/v1/checkouts/{cid}/",
            {"email": "alice@orders.test"},
            format="json",
        )
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        oid = r.data["id"]

        r = self.client.get("/api/v1/orders/", **h_b)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.data["results"] if isinstance(r.data, dict) and "results" in r.data else r.data
        self.assertEqual(rows, [])

        r = self.client.get(f"/api/v1/orders/{oid}/", **h_b)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

        r = self.client.get(f"/api/v1/orders/{oid}/", **h_a)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["email"], "alice@orders.test")

    def test_authenticated_buyer_sees_order_placed_while_logged_in(self):
        h = self._register_and_headers("carol@orders.test", "Piano-Cloud-7-Violet!")
        r = self.client.post("/api/v1/checkouts/", {}, format="json", **h)
        cid = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json", **h)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        oid = r.data["id"]

        r = self.client.get("/api/v1/orders/", **h)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.data["results"] if isinstance(r.data, dict) and "results" in r.data else r.data
        ids = [o["id"] for o in rows]
        self.assertIn(oid, ids)


class FulfillmentTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(title="FC", is_active=True)
        self.product = Product.objects.create(
            title="Item",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title="V",
            sku="SKU-F",
            price=Decimal("10.00"),
            inventory_quantity=10,
            is_active=True,
        )
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="orderstaff",
            email="orderstaff@example.com",
            password="OrderStaff1!",
            is_staff=True,
        )

    def _complete_order(self):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        cid = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.variant.id, "quantity": 3},
            format="json",
        )
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        return r.data["id"]

    def test_order_api_includes_fulfillment_status(self):
        oid = self._complete_order()
        self.client.force_authenticate(self.staff)
        r = self.client.get(f"/api/v1/orders/{oid}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["fulfillment_status"], FULFILLMENT_STATUS_UNFULFILLED)
        self.assertEqual(r.data["fulfillment_status_label"], "Unfulfilled")
        self.assertEqual(r.data["financial_status_label"], "Paid")
        self.assertEqual(r.data["fulfillments"], [])
        self.assertEqual(r.data["order_number"], 1000)
        self.assertEqual(r.data["name"], "#1000")
        li = r.data["line_items"][0]
        self.assertEqual(li["fulfillment_status"], FULFILLMENT_STATUS_UNFULFILLED)
        self.assertEqual(li["fulfillment_status_label"], "Unfulfilled")
        self.assertIn("variant_detail", li)

    def test_fulfillment_line_validates_quantity(self):
        oid = self._complete_order()
        order = Order.objects.get(pk=oid)
        oli = order.line_items.get()
        svc = FulfillmentService.objects.create(
            name="Express",
            courier_name="Test Courier",
            carrier_code="test",
        )
        f1 = Fulfillment.objects.create(order=order, fulfillment_service=svc, status=SHIPMENT_STATUS_PENDING)
        FulfillmentLineItem.objects.create(fulfillment=f1, order_line_item=oli, quantity=2)
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_UNFULFILLED)

        f2 = Fulfillment.objects.create(order=order, fulfillment_service=svc, status=SHIPMENT_STATUS_PENDING)
        line = FulfillmentLineItem(fulfillment=f2, order_line_item=oli, quantity=2)
        with self.assertRaises(ValidationError):
            line.full_clean()

        f1.status = SHIPMENT_STATUS_SUCCESS
        f1.save()
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_PARTIAL)

        f1.status = SHIPMENT_STATUS_CANCELLED
        f1.save()
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_UNFULFILLED)

        FulfillmentLineItem.objects.filter(fulfillment=f1).delete()
        f1.delete()
        FulfillmentLineItem.objects.create(fulfillment=f2, order_line_item=oli, quantity=3)
        f2.status = SHIPMENT_STATUS_SUCCESS
        f2.save()
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_FULFILLED)

    def test_order_fully_delivered_different_tracking_is_partial(self):
        oid = self._complete_order()
        order = Order.objects.get(pk=oid)
        oli = order.line_items.get()
        svc = FulfillmentService.objects.create(
            name="Express",
            courier_name="Test Courier",
            carrier_code="test",
        )
        f1 = Fulfillment.objects.create(
            order=order,
            fulfillment_service=svc,
            tracking_number="TRACK-A",
            status=SHIPMENT_STATUS_SUCCESS,
        )
        FulfillmentLineItem.objects.create(fulfillment=f1, order_line_item=oli, quantity=1)
        f2 = Fulfillment.objects.create(
            order=order,
            fulfillment_service=svc,
            tracking_number="TRACK-B",
            status=SHIPMENT_STATUS_SUCCESS,
        )
        FulfillmentLineItem.objects.create(fulfillment=f2, order_line_item=oli, quantity=2)
        self.assertEqual(get_order_line_fulfillment_state(oli), FULFILLMENT_STATUS_FULFILLED)
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_PARTIAL)

        f2.tracking_number = "TRACK-A"
        f2.save()
        self.assertEqual(get_order_fulfillment_state(order), FULFILLMENT_STATUS_FULFILLED)


class FulfillmentApiTests(TestCase):
    """POST /orders/{id}/fulfillments/ — Shopify-style complete, partial, manual (staff only)."""

    def setUp(self):
        self.collection = Collection.objects.create(title="FC", is_active=True)
        self.product_a = Product.objects.create(
            title="Item",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.product_b = Product.objects.create(
            title="Item B",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.v1 = ProductVariant.objects.create(
            product=self.product_a,
            title="V1",
            sku="SKU-1",
            price=Decimal("10.00"),
            inventory_quantity=10,
            is_active=True,
        )
        self.v2 = ProductVariant.objects.create(
            product=self.product_b,
            title="V2",
            sku="SKU-2",
            price=Decimal("5.00"),
            inventory_quantity=10,
            is_active=True,
        )
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="merchant",
            email="merchant@example.com",
            password="MerchantPass1!",
            is_staff=True,
        )
        self.svc = FulfillmentService.objects.create(
            name="Express",
            courier_name="Test Courier",
            carrier_code="test",
        )

    def _checkout_with_two_lines(self):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        cid = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.v1.id, "quantity": 2},
            format="json",
        )
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.v2.id, "quantity": 3},
            format="json",
        )
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        return r.data["id"]

    def test_fulfillment_create_requires_staff(self):
        oid = self._checkout_with_two_lines()
        r = self.client.post(
            f"/api/v1/orders/{oid}/fulfillments/",
            {"scope": FULFILLMENT_CREATE_SCOPE_COMPLETE, "manual": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fulfillment_inventory_requires_staff(self):
        oid = self._checkout_with_two_lines()
        r = self.client.get(f"/api/v1/orders/{oid}/fulfillment-inventory/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manual_complete_fulfillment(self):
        oid = self._checkout_with_two_lines()
        self.client.force_authenticate(self.staff)
        r = self.client.get(f"/api/v1/orders/{oid}/fulfillment-inventory/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(r.data[0]["quantity_remaining_allocatable"], 2)
        self.assertEqual(r.data[1]["quantity_remaining_allocatable"], 3)
        self.assertEqual(r.data[0]["fulfillment_status"], FULFILLMENT_STATUS_UNFULFILLED)
        self.assertEqual(r.data[1]["fulfillment_status"], FULFILLMENT_STATUS_UNFULFILLED)

        r = self.client.post(
            f"/api/v1/orders/{oid}/fulfillments/",
            {"scope": FULFILLMENT_CREATE_SCOPE_COMPLETE, "manual": True, "notify_customer": False},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIsNone(r.data["fulfillment_service"])
        self.assertEqual(len(r.data["line_items"]), 2)
        self.assertEqual(r.data["status"], SHIPMENT_STATUS_SUCCESS)

        r = self.client.get(f"/api/v1/orders/{oid}/")
        self.assertEqual(r.data["fulfillment_status"], FULFILLMENT_STATUS_FULFILLED)
        for li in r.data["line_items"]:
            self.assertEqual(li["fulfillment_status"], FULFILLMENT_STATUS_FULFILLED)

    def test_partial_then_complete_carrier(self):
        oid = self._checkout_with_two_lines()
        order = Order.objects.get(pk=oid)
        lines = list(order.line_items.order_by("id"))
        self.client.force_authenticate(self.staff)

        r = self.client.post(
            f"/api/v1/orders/{oid}/fulfillments/",
            {
                "scope": FULFILLMENT_CREATE_SCOPE_PARTIAL,
                "manual": False,
                "fulfillment_service": self.svc.id,
                "status": SHIPMENT_STATUS_SUCCESS,
                "line_items": [
                    {"order_line_item": lines[0].pk, "quantity": 1},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["fulfillment_service"], self.svc.id)
        r = self.client.get(f"/api/v1/orders/{oid}/")
        self.assertEqual(r.data["fulfillment_status"], FULFILLMENT_STATUS_PARTIAL)

        r = self.client.post(
            f"/api/v1/orders/{oid}/fulfillments/",
            {
                "scope": FULFILLMENT_CREATE_SCOPE_COMPLETE,
                "manual": False,
                "fulfillment_service": self.svc.id,
                "line_items": [
                    {"order_line_item": lines[0].pk, "quantity": 1},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

        r = self.client.post(
            f"/api/v1/orders/{oid}/fulfillments/",
            {
                "scope": FULFILLMENT_CREATE_SCOPE_COMPLETE,
                "manual": False,
                "fulfillment_service": self.svc.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(len(r.data["line_items"]), 2)
        r = self.client.get(f"/api/v1/orders/{oid}/")
        self.assertEqual(r.data["fulfillment_status"], FULFILLMENT_STATUS_FULFILLED)


class SizeChartApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tag = Tag.objects.create(name="SizeChartTag")
        self.chart = SizeChart.objects.create(tag=self.tag, title="Tops", is_active=True)
        self.row_s = SizeChartRow.objects.create(chart=self.chart, sort_order=0, label="S")
        self.row_m = SizeChartRow.objects.create(chart=self.chart, sort_order=1, label="M")
        self.col_us = SizeChartColumn.objects.create(chart=self.chart, sort_order=0, label="US")
        self.col_eu = SizeChartColumn.objects.create(chart=self.chart, sort_order=1, label="EU")
        SizeChartCell.objects.create(
            chart=self.chart, row=self.row_s, column=self.col_us, value="4"
        )
        SizeChartCell.objects.create(
            chart=self.chart, row=self.row_s, column=self.col_eu, value="36"
        )
        SizeChartCell.objects.create(
            chart=self.chart, row=self.row_m, column=self.col_us, value="6"
        )

    def test_size_chart_by_tag_returns_grid(self):
        r = self.client.get(
            "/api/v1/size-charts/by-tag/",
            {"name": "sizecharttag"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["tag"]["name"], "SizeChartTag")
        self.assertEqual(r.data["title"], "Tops")
        self.assertEqual(len(r.data["columns"]), 2)
        self.assertEqual(len(r.data["rows"]), 2)
        self.assertEqual(r.data["rows"][0]["label"], "S")
        vals_s = r.data["rows"][0]["values"]
        self.assertEqual(len(vals_s), 2)
        self.assertEqual(vals_s[0]["value"], "4")
        self.assertEqual(vals_s[1]["value"], "36")
        self.assertEqual(r.data["rows"][1]["values"][0]["value"], "6")
        self.assertEqual(r.data["rows"][1]["values"][1]["value"], "")

    def test_size_chart_by_tag_requires_name(self):
        r = self.client.get("/api/v1/size-charts/by-tag/")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_size_chart_by_tag_unknown_tag(self):
        r = self.client.get("/api/v1/size-charts/by-tag/", {"name": "missing"})
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_size_chart_by_tag_no_chart(self):
        orphan = Tag.objects.create(name="NoChart")
        r = self.client.get("/api/v1/size-charts/by-tag/", {"name": orphan.name})
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_size_chart_by_tag_inactive(self):
        self.chart.is_active = False
        self.chart.save()
        r = self.client.get("/api/v1/size-charts/by-tag/", {"name": self.tag.name})
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_size_chart_cell_clean_rejects_mismatched_row_column_chart(self):
        other_tag = Tag.objects.create(name="OtherTag")
        other_chart = SizeChart.objects.create(tag=other_tag, title="Other")
        foreign_col = SizeChartColumn.objects.create(chart=other_chart, sort_order=0, label="X")
        cell = SizeChartCell(
            chart=self.chart,
            row=self.row_s,
            column=foreign_col,
            value="bad",
        )
        with self.assertRaises(ValidationError):
            cell.full_clean()


class SizeChartGridServiceTests(TestCase):
    def test_apply_and_export_round_trip(self):
        tag = Tag.objects.create(name="GridSvc")
        chart = SizeChart.objects.create(tag=tag, title="T")
        payload = {
            "column_labels": ["CHEST", "WAIST", "HIP"],
            "rows": [
                {"label": "S", "values": ["23", "32", "36"]},
                {"label": "M", "values": ["25", "", ""]},
                {"label": "L", "values": ["", "", ""]},
            ],
        }
        apply_grid_payload_to_chart(chart, payload)
        chart.refresh_from_db()
        out = chart_to_grid_dict(chart)
        self.assertEqual(out["column_labels"], ["CHEST", "WAIST", "HIP"])
        self.assertEqual(len(out["rows"]), 3)
        self.assertEqual(out["rows"][0]["label"], "S")
        self.assertEqual(out["rows"][0]["values"], ["23", "32", "36"])
        self.assertEqual(out["rows"][1]["values"], ["25", "", ""])

    def test_validate_rejects_ragged_row(self):
        with self.assertRaises(ValueError):
            validate_grid_payload(
                {"column_labels": ["A", "B"], "rows": [{"label": "x", "values": ["1"]}]}
            )


STRIPE_TEST_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "STRIPE_PUBLISHABLE_KEY": "pk_test_fake",
    "STRIPE_WEBHOOK_SECRET": "whsec_fake",
}


@override_settings(**STRIPE_TEST_SETTINGS)
class StripeCheckoutApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        CheckoutPaymentSettings.objects.update_or_create(
            pk=1,
            defaults={
                "stripe_checkout_enabled": True,
                "allow_cod_complete": False,
            },
        )
        self.collection = Collection.objects.create(title="Stripe", is_active=True)
        self.product = Product.objects.create(
            title="Paid Item",
            collection=self.collection,
            status="active",
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title="Default",
            sku="STRIPE-1",
            price=Decimal("25.00"),
            inventory_quantity=5,
            is_active=True,
        )

    def _open_checkout_with_line(self, email="pay@example.com"):
        r = self.client.post("/api/v1/checkouts/", {}, format="json")
        cid = r.data["id"]
        self.client.post(
            "/api/v1/checkout-line-items/",
            {"checkout": cid, "variant": self.variant.id, "quantity": 1},
            format="json",
        )
        self.client.patch(
            f"/api/v1/checkouts/{cid}/",
            {"email": email},
            format="json",
        )
        return cid

    def test_complete_blocked_when_stripe_enabled_and_amount_due(self):
        cid = self._open_checkout_with_line()
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment", str(r.data).lower())

    @override_settings(
        STOREFRONT_BASE_URL="http://localhost:5173",
        STOREFRONT_CHECKOUT_SUCCESS_PATH="/checkout/success",
        STOREFRONT_CHECKOUT_CANCEL_PATH="/checkout/cancel",
    )
    @patch("ecommerce.services.stripe_checkout.stripe.checkout.Session.create")
    @patch("ecommerce.services.stripe_checkout.stripe.Coupon.create")
    def test_payment_session_returns_checkout_url(self, mock_coupon, mock_session_create):
        mock_coupon.return_value = MagicMock(id="coupon_test")
        mock_session_create.return_value = MagicMock(
            id="cs_test_abc",
            url="https://checkout.stripe.com/pay/cs_test_abc",
        )
        cid = self._open_checkout_with_line()
        r = self.client.post(
            f"/api/v1/checkouts/{cid}/payment-session/",
            {},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["session_id"], "cs_test_abc")
        self.assertIn("checkout.stripe.com", r.data["checkout_url"])
        checkout = Checkout.objects.get(pk=cid)
        self.assertEqual(checkout.stripe_checkout_session_id, "cs_test_abc")
        call_kwargs = mock_session_create.call_args.kwargs
        self.assertIn("{CHECKOUT_SESSION_ID}", call_kwargs["success_url"])
        self.assertTrue(call_kwargs["success_url"].startswith("http://localhost:5173/checkout/success"))
        self.assertEqual(call_kwargs["cancel_url"], "http://localhost:5173/checkout/cancel")

    @patch("ecommerce.services.stripe_checkout.stripe.checkout.Session.retrieve")
    def test_session_confirm_creates_paid_order(self, mock_retrieve):
        cid = self._open_checkout_with_line()
        checkout = Checkout.objects.get(pk=cid)
        checkout.stripe_checkout_session_id = "cs_test_paid"
        checkout.save()

        mock_retrieve.return_value = MagicMock(
            id="cs_test_paid",
            payment_status="paid",
            payment_intent="pi_test_123",
            metadata={"checkout_id": str(cid)},
        )

        r = self.client.get("/api/v1/stripe/session/cs_test_paid/confirm/")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["financial_status"], "paid")
        self.assertEqual(r.data["stripe_payment_intent_id"], "pi_test_123")
        checkout.refresh_from_db()
        self.assertEqual(checkout.status, CHECKOUT_STATUS_COMPLETED)

    def test_stripe_config_endpoint(self):
        r = self.client.get("/api/v1/stripe/config/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["enabled"])
        self.assertEqual(r.data["publishable_key"], "pk_test_fake")
        self.assertIn("payment_options", r.data)
        self.assertTrue(r.data["payment_options"]["stripe_checkout"])
        self.assertFalse(r.data["payment_options"]["cod"])
        self.assertTrue(r.data["stripe"]["stripe_checkout_available"])
        effective = r.data["payment_options"]["effective_checkout_urls"]
        self.assertIn("{CHECKOUT_SESSION_ID}", effective["success_url"])
        self.assertIn("/checkout/success", effective["success_url"])
        self.assertIn("/checkout/cancel", effective["cancel_url"])

    @override_settings(**STRIPE_TEST_SETTINGS)
    def test_cod_complete_when_enabled_in_admin(self):
        CheckoutPaymentSettings.objects.update_or_create(
            pk=1,
            defaults={
                "stripe_checkout_enabled": True,
                "allow_cod_complete": True,
            },
        )
        cid = self._open_checkout_with_line()
        r = self.client.post(f"/api/v1/checkouts/{cid}/complete/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["financial_status"], "pending")

    @override_settings(STRIPE_SECRET_KEY="", STRIPE_PUBLISHABLE_KEY="")
    def test_stripe_config_shows_unavailable_reason_without_keys(self):
        CheckoutPaymentSettings.objects.update_or_create(
            pk=1,
            defaults={"stripe_checkout_enabled": True, "allow_cod_complete": False},
        )
        r = self.client.get("/api/v1/stripe/config/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["enabled"])
        self.assertTrue(r.data["payment_options"]["stripe_checkout"])
        self.assertFalse(r.data["payment_options"]["stripe_checkout_available"])
        self.assertIn("STRIPE_SECRET_KEY", r.data["payment_options"]["stripe_unavailable_reason"])


class CheckoutRedirectUrlTests(TestCase):
    @override_settings(
        STOREFRONT_BASE_URL="http://localhost:5173",
        STOREFRONT_CHECKOUT_SUCCESS_PATH="/checkout/success",
        STOREFRONT_CHECKOUT_CANCEL_PATH="/checkout/cancel",
    )
    def test_build_vite_redirect_urls(self):
        from ecommerce.services.checkout_payment_settings import build_checkout_redirect_urls

        urls = build_checkout_redirect_urls()
        self.assertEqual(
            urls["success_url"],
            "http://localhost:5173/checkout/success?session_id={CHECKOUT_SESSION_ID}",
        )
        self.assertEqual(urls["cancel_url"], "http://localhost:5173/checkout/cancel")


class ShopifyCsvImportTests(TestCase):
    def test_import_bundled_shopify_template_without_images(self):
        from pathlib import Path

        from ecommerce.shopify_csv_import import load_shopify_product_csv

        csv_path = Path(__file__).resolve().parent / "fixtures" / "product_template.csv"
        self.assertTrue(csv_path.is_file(), msg=f"Missing fixture {csv_path}")

        stats = load_shopify_product_csv(csv_path, download_images=False)
        self.assertEqual(stats["groups"], 3)
        self.assertGreaterEqual(stats["variants_created"], 10)
        self.assertTrue(
            Product.objects.filter(handle="physical-product-the-band-t-shirt").exists()
        )
        v = ProductVariant.objects.get(sku="TheBandTShirt-SG")
        self.assertEqual(v.barcode, "5784397765")
        self.assertEqual(v.price, Decimal("19.99"))
        band = Product.objects.get(handle="physical-product-the-band-t-shirt")
        self.assertIn("Apparel", band.product_category)
        self.assertTrue(band.description)
        self.assertFalse(band.gift_card)

    def test_import_classic_shopify_apparel_csv_without_images(self):
        from pathlib import Path

        from ecommerce.shopify_csv_import import load_shopify_product_csv

        csv_path = Path(__file__).resolve().parent / "fixtures" / "apparel.csv"
        self.assertTrue(csv_path.is_file(), msg=f"Missing fixture {csv_path}")

        stats = load_shopify_product_csv(csv_path, download_images=False)
        self.assertEqual(stats["groups"], 20)
        self.assertGreaterEqual(stats["variants_created"], 20)
        self.assertTrue(Product.objects.filter(handle="ocean-blue-shirt").exists())
        ocean = Product.objects.get(handle="ocean-blue-shirt")
        self.assertEqual(ocean.variants.count(), 1)
        self.assertEqual(ocean.variants.first().price, Decimal("50"))

    def test_import_home_and_garden_sets_body_html(self):
        from pathlib import Path

        from ecommerce.shopify_csv_import import load_shopify_product_csv

        csv_path = Path(__file__).resolve().parent / "fixtures" / "home-and-garden.csv"
        self.assertTrue(csv_path.is_file())
        load_shopify_product_csv(csv_path, download_images=False)
        pot = Product.objects.get(handle="clay-plant-pot")
        self.assertIn("clay", pot.body_html.lower())
        self.assertIn("clay", pot.description.lower())

    def test_import_classic_shopify_jewelery_skips_image_only_rows(self):
        from pathlib import Path

        from ecommerce.shopify_csv_import import load_shopify_product_csv

        csv_path = Path(__file__).resolve().parent / "fixtures" / "jewelery.csv"
        self.assertTrue(csv_path.is_file(), msg=f"Missing fixture {csv_path}")

        stats = load_shopify_product_csv(csv_path, download_images=False)
        self.assertEqual(stats["groups"], 20)
        self.assertEqual(stats["variants_created"], 23)
        leather = Product.objects.get(handle="leather-anchor")
        self.assertEqual(leather.variants.count(), 2)


class SoftDeleteProductTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(title="SoftDel", is_active=True)
        self.product = Product.objects.create(
            title="Widget",
            collection=self.collection,
            handle="soft-del-widget",
            status="active",
            is_published=True,
        )

    def test_soft_delete_hides_from_default_manager(self):
        self.product.delete()
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        hidden = Product.all_objects.get(pk=self.product.pk)
        self.assertIsNotNone(hidden.deleted_at)

    def test_restore_brings_back_to_default_manager(self):
        self.product.delete()
        Product.all_objects.get(pk=self.product.pk).restore()
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_same_handle_allowed_after_soft_delete(self):
        self.product.delete()
        replacement = Product.objects.create(
            title="Widget 2",
            collection=self.collection,
            handle="soft-del-widget",
            status="active",
            is_published=True,
        )
        self.assertEqual(replacement.handle, "soft-del-widget")

    def test_duplicate_title_gets_timestamp_suffix_handle(self):
        Product.objects.create(
            title="Same Title",
            collection=self.collection,
            handle="same-title",
            status="active",
            is_published=True,
        )
        second = Product.objects.create(
            title="Same Title",
            collection=self.collection,
            handle="same-title",
            status="active",
            is_published=True,
        )
        self.assertTrue(second.handle.startswith("same-title-"))
        self.assertNotEqual(second.handle, "same-title")

    def test_soft_deleted_collection_same_handle_recreate(self):
        c = Collection.objects.create(title="Col", handle="col-h", is_active=True)
        c.delete()
        c2 = Collection.objects.create(title="Col2", handle="col-h", is_active=True)
        self.assertEqual(c2.handle, "col-h")

