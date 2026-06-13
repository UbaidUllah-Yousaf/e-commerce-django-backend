# ecommerce/views.py

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ecommerce.filters import CollectionFilter
from ecommerce.models.collection import Collection
from ecommerce.serializers.collection import CollectionSerializer


# =========================================================
# COLLECTION VIEWSET
# =========================================================

class CollectionViewSet(viewsets.ModelViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    permission_classes = [AllowAny]
    filterset_class = CollectionFilter
    ordering_fields = (
        "title",
        "handle",
        "created_at",
        "updated_at",
        "id",
    )


