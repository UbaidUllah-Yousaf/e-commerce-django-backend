from rest_framework import serializers


class SizeChartTagSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class SizeChartColumnOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sort_order = serializers.IntegerField()
    label = serializers.CharField()


class SizeChartCellValueSerializer(serializers.Serializer):
    column_id = serializers.IntegerField()
    value = serializers.CharField()


class SizeChartRowOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sort_order = serializers.IntegerField()
    label = serializers.CharField()
    values = SizeChartCellValueSerializer(many=True)


class SizeChartByTagSerializer(serializers.Serializer):
    tag = SizeChartTagSerializer()
    title = serializers.CharField(allow_blank=True)
    columns = SizeChartColumnOutSerializer(many=True)
    rows = SizeChartRowOutSerializer(many=True)
