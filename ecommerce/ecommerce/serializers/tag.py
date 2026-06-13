# =========================================================
# TAG
# =========================================================
from rest_framework import serializers

from ecommerce.models.tag import Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
