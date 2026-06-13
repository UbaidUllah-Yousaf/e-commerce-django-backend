# =========================================================
# TAG VIEWSET
# =========================================================
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ecommerce.filters import TagFilter
from ecommerce.models.tag import Tag
from ecommerce.serializers.tag import TagSerializer


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    filterset_class = TagFilter
    ordering_fields = ("name", "created_at", "updated_at", "id")


