from rest_framework import serializers

from ecommerce.models.collection import Collection


# =========================================================
# COLLECTION
# =========================================================
class CollectionSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = "__all__"

    def get_products_count(self, obj):
        return obj.product_set.count()

