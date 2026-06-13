from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ecommerce.filters import GiftCardFilter
from ecommerce.models.gift_card import GiftCard
from ecommerce.serializers.gift_card import GiftCardSerializer


class GiftCardViewSet(viewsets.ModelViewSet):
    queryset = GiftCard.objects.all()
    serializer_class = GiftCardSerializer
    permission_classes = [AllowAny]
    filterset_class = GiftCardFilter
    ordering_fields = (
        "code",
        "initial_balance",
        "current_balance",
        "created_at",
        "updated_at",
        "expires_at",
        "id",
    )
