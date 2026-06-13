import django_filters

from ecommerce.models.checkout import Checkout, CheckoutLineItem, Order
from ecommerce.models.collection import Collection
from ecommerce.models.customer import CustomerAddress
from ecommerce.models.discount import DiscountCode
from ecommerce.models.gift_card import GiftCard
from ecommerce.models.product import Product, ProductOption, ProductOptionValue, ProductVariant
from ecommerce.models.tag import Tag


class CollectionFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Collection
        fields = {
            "is_active": ["exact"],
            "handle": ["exact", "icontains"],
        }


class TagFilter(django_filters.FilterSet):
    class Meta:
        model = Tag
        fields = {
            "name": ["exact", "icontains"],
        }


class ProductFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    tag = django_filters.NumberFilter(method="filter_by_tag_id")

    product_category = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Product
        fields = {
            "status": ["exact"],
            "collection": ["exact"],
            "is_published": ["exact"],
            "gift_card": ["exact"],
            "published_scope": ["exact"],
            "vendor": ["exact", "icontains"],
            "product_type": ["exact", "icontains"],
        }

    def filter_by_tag_id(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(tags__id=value).distinct()


class ProductVariantFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    sku = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ProductVariant
        fields = {
            "product": ["exact"],
            "is_active": ["exact"],
        }


class ProductOptionFilter(django_filters.FilterSet):
    class Meta:
        model = ProductOption
        fields = {
            "product": ["exact"],
            "name": ["exact", "icontains"],
        }


class ProductOptionValueFilter(django_filters.FilterSet):
    value = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ProductOptionValue
        fields = {
            "option": ["exact"],
        }


class CheckoutFilter(django_filters.FilterSet):
    email = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Checkout
        fields = {
            "status": ["exact"],
            "currency": ["exact"],
        }


class CheckoutLineItemFilter(django_filters.FilterSet):
    class Meta:
        model = CheckoutLineItem
        fields = {
            "checkout": ["exact"],
            "variant": ["exact"],
        }


class OrderFilter(django_filters.FilterSet):
    token = django_filters.UUIDFilter()
    email = django_filters.CharFilter(lookup_expr="icontains")
    name = django_filters.CharFilter(lookup_expr="icontains")
    order_number = django_filters.NumberFilter()

    class Meta:
        model = Order
        fields = {
            "financial_status": ["exact"],
            "currency": ["exact"],
            "order_number": ["exact"],
        }


class DiscountCodeFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(lookup_expr="icontains")
    title = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = DiscountCode
        fields = {
            "discount_type": ["exact"],
            "is_active": ["exact"],
        }


class GiftCardFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = GiftCard
        fields = {
            "currency": ["exact"],
            "is_active": ["exact"],
        }


class CustomerAddressFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr="icontains")
    zip = django_filters.CharFilter(field_name="zip", lookup_expr="icontains")
    country_code = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = CustomerAddress
        fields = {
            "is_default_shipping": ["exact"],
            "is_default_billing": ["exact"],
        }
