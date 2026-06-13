from django.test import TestCase

from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.rules.city_router import CityRouterError, select_courier


class CityRouterTests(TestCase):
    def setUp(self):
        CourierConfiguration.objects.create(courier_name="TCS", is_active=True)
        CourierConfiguration.objects.create(courier_name="Leopard", is_active=True)
        CourierConfiguration.objects.create(courier_name="FallbackCo", is_active=True)
        CityFulfillmentRule.objects.create(
            city_name="Lahore",
            priority=1,
            courier_name="TCS",
            service_type="partner_next_day",
        )
        CityFulfillmentRule.objects.create(
            city_name="Karachi",
            priority=2,
            courier_name="Leopard",
            service_type="partner_same_day",
        )
        CityFulfillmentRule.objects.create(
            city_name="*",
            priority=99,
            courier_name="FallbackCo",
            service_type="partner_next_day",
        )

    def test_lahore_selects_highest_priority(self):
        sel = select_courier("Lahore")
        self.assertEqual(sel.courier_name, "TCS")
        self.assertEqual(sel.service_type, "partner_next_day")

    def test_unknown_city_uses_fallback_rule(self):
        sel = select_courier("Islamabad")
        self.assertEqual(sel.courier_name, "FallbackCo")

    def test_courier_override_wins(self):
        sel = select_courier("Lahore", courier_override="Leopard")
        self.assertEqual(sel.courier_name, "Leopard")

    def test_no_match_without_fallback_raises(self):
        CityFulfillmentRule.objects.all().delete()
        CourierConfiguration.objects.all().delete()
        with self.assertRaises(CityRouterError):
            select_courier("Lahore")
