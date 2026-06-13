# ecommerce/router.py

from ecommerce.views.customer import CustomerAddressViewSet
from ecommerce.views.checkout import (
    CheckoutLineItemViewSet,
    CheckoutViewSet,
    OrderViewSet,
)
from ecommerce.views.collection import CollectionViewSet
from ecommerce.views.discount import DiscountCodeViewSet
from ecommerce.views.gift_card import GiftCardViewSet
from ecommerce.views.product import ProductViewSet, ProductVariantViewSet, ProductOptionViewSet, \
    ProductOptionValueViewSet
from ecommerce.views.tag import TagViewSet


def get_api_routes(router):
    router.register(
        r"collections",
        CollectionViewSet,
        basename="collections"
    )
    router.register(
        r"products",
        ProductViewSet,
        basename="products"
    )
    router.register(
        r"variants",
        ProductVariantViewSet,
        basename="variants"
    )
    router.register(
        r"options",
        ProductOptionViewSet,
        basename="options"
    )
    router.register(
        r"option-values",
        ProductOptionValueViewSet,
        basename="option-values"
    )
    router.register(
        r"tags",
        TagViewSet,
        basename="tags"
    )
    router.register(
        r"checkouts",
        CheckoutViewSet,
        basename="checkouts"
    )
    router.register(
        r"checkout-line-items",
        CheckoutLineItemViewSet,
        basename="checkout-line-items"
    )
    router.register(
        r"orders",
        OrderViewSet,
        basename="orders"
    )
    router.register(
        r"discount-codes",
        DiscountCodeViewSet,
        basename="discount-codes"
    )
    router.register(
        r"gift-cards",
        GiftCardViewSet,
        basename="gift-cards"
    )
    router.register(
        r"customers/me/addresses",
        CustomerAddressViewSet,
        basename="customer-addresses",
    )

