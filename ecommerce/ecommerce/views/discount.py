from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ecommerce.filters import DiscountCodeFilter
from ecommerce.models.discount import DiscountCode
from ecommerce.serializers.discount import DiscountCodeSerializer


class DiscountCodeViewSet(viewsets.ModelViewSet):
    queryset = DiscountCode.objects.all()
    serializer_class = DiscountCodeSerializer
    permission_classes = [AllowAny]
    filterset_class = DiscountCodeFilter
    ordering_fields = ("code", "created_at", "updated_at", "value", "usage_count", "id")
