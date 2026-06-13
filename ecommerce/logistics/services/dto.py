from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class NormalizedOrderDTO:
    source_platform: str
    external_order_id: str
    order_number: str = ""
    shop_id: int | None = None
    ecommerce_order_id: int | None = None
    customer_payload: dict = field(default_factory=dict)
    shipping_address: dict = field(default_factory=dict)
    line_items: list = field(default_factory=list)
    city: str = ""
    cod_amount: Decimal | None = None
