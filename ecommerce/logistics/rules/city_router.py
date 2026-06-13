from dataclasses import dataclass

from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.utils.city import normalize_city_name


@dataclass(frozen=True)
class CourierSelection:
    courier_name: str
    service_type: str
    rule_city: str = ""


class CityRouterError(Exception):
    pass


def _courier_available(courier_name: str, city_normalized: str) -> bool:
    courier = CourierConfiguration.objects.filter(
        courier_name=courier_name,
        is_active=True,
    ).first()
    if not courier:
        return False
    cities = courier.supported_cities or []
    if not cities:
        return True
    supported = {normalize_city_name(c) for c in cities}
    return city_normalized in supported or "*" in supported


def select_courier(
    city: str,
    *,
    courier_override: str = "",
) -> CourierSelection:
    if courier_override:
        courier = CourierConfiguration.objects.filter(
            courier_name=courier_override,
            is_active=True,
        ).first()
        if not courier:
            raise CityRouterError(f"Override courier '{courier_override}' is not active.")
        rule = (
            CityFulfillmentRule.objects.filter(
                courier_name=courier_override,
                is_active=True,
            )
            .order_by("priority")
            .first()
        )
        service_type = rule.service_type if rule else "partner_next_day"
        return CourierSelection(
            courier_name=courier_override,
            service_type=service_type,
            rule_city="override",
        )

    city_norm = normalize_city_name(city)
    rules = CityFulfillmentRule.objects.filter(is_active=True).order_by("priority", "city_name")

    for rule in rules:
        rule_city_norm = normalize_city_name(rule.city_name)
        if rule_city_norm not in (city_norm, "*"):
            continue
        if not _courier_available(rule.courier_name, city_norm):
            continue
        return CourierSelection(
            courier_name=rule.courier_name,
            service_type=rule.service_type,
            rule_city=rule.city_name,
        )

    config = FulfillmentConfiguration.get_solo()
    fallback = config.default_fallback_courier
    if fallback and fallback.is_active:
        rule = (
            CityFulfillmentRule.objects.filter(
                courier_name=fallback.courier_name,
                is_active=True,
            )
            .order_by("priority")
            .first()
        )
        service_type = rule.service_type if rule else "partner_next_day"
        return CourierSelection(
            courier_name=fallback.courier_name,
            service_type=service_type,
            rule_city="fallback",
        )

    raise CityRouterError(f"No courier rule matched for city '{city}' and no fallback configured.")
