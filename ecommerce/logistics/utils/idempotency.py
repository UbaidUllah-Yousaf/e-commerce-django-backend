from logistics.constants import SOURCE_PLATFORM_ECOMMERCE, SOURCE_PLATFORM_SHOPIFY


def build_idempotency_key(
    source_platform: str,
    external_order_id: str,
    shop_id: int | None = None,
) -> str:
    shop_part = str(shop_id) if shop_id else "native"
    return f"{source_platform}:{shop_part}:{external_order_id}"
