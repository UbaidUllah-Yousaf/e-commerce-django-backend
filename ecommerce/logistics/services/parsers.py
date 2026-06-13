from decimal import Decimal

from logistics.constants import SOURCE_PLATFORM_ECOMMERCE, SOURCE_PLATFORM_SHOPIFY
from logistics.services.dto import NormalizedOrderDTO
from logistics.utils.city import extract_city_from_address


def parse_shopify_order(payload: dict, shop_id: int) -> NormalizedOrderDTO:
    shipping = payload.get("shipping_address") or {}
    customer = {
        "email": payload.get("email") or shipping.get("email") or "",
        "phone": payload.get("phone") or shipping.get("phone") or "",
        "first_name": shipping.get("first_name") or "",
        "last_name": shipping.get("last_name") or "",
        "name": f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
    }
    line_items = []
    for li in payload.get("line_items") or []:
        line_items.append(
            {
                "title": li.get("title") or li.get("name"),
                "sku": li.get("sku") or "",
                "quantity": li.get("quantity", 1),
                "price": li.get("price"),
            }
        )
    cod_amount = None
    if payload.get("financial_status") == "pending":
        cod_amount = Decimal(str(payload.get("total_price") or "0"))

    return NormalizedOrderDTO(
        source_platform=SOURCE_PLATFORM_SHOPIFY,
        external_order_id=str(payload.get("id") or ""),
        order_number=str(payload.get("name") or payload.get("order_number") or ""),
        shop_id=shop_id,
        customer_payload=customer,
        shipping_address=shipping,
        line_items=line_items,
        city=extract_city_from_address(shipping),
        cod_amount=cod_amount,
    )


def parse_ecommerce_order(order) -> NormalizedOrderDTO:
    shipping = order.shipping_address or {}
    line_items = []
    for oli in order.line_items.all():
        line_items.append(
            {
                "title": oli.product_title,
                "variant_title": oli.variant_title,
                "sku": oli.sku,
                "quantity": oli.quantity,
                "price": str(oli.unit_price),
            }
        )
    cod_amount = None
    if order.financial_status == "pending":
        cod_amount = order.total

    return NormalizedOrderDTO(
        source_platform=SOURCE_PLATFORM_ECOMMERCE,
        external_order_id=str(order.pk),
        order_number=order.name,
        ecommerce_order_id=order.pk,
        customer_payload={
            "email": order.email,
            "phone": order.phone,
            "name": order.email,
        },
        shipping_address=shipping,
        line_items=line_items,
        city=extract_city_from_address(shipping),
        cod_amount=cod_amount,
    )
