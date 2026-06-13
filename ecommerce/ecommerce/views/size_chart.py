from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.models.size_chart import SizeChart, SizeChartCell
from ecommerce.models.tag import Tag
from ecommerce.serializers.size_chart import SizeChartByTagSerializer


def _serialize_size_chart(chart: SizeChart) -> dict:
    columns = [
        {"id": c.id, "sort_order": c.sort_order, "label": c.label}
        for c in sorted(chart.columns.all(), key=lambda x: (x.sort_order, x.id))
    ]
    col_ids = [c["id"] for c in columns]
    cells_by_row: dict[int, dict[int, str]] = {}
    for cell in chart.cells.all():
        cells_by_row.setdefault(cell.row_id, {})[cell.column_id] = cell.value

    rows_out = []
    for row in sorted(chart.rows.all(), key=lambda x: (x.sort_order, x.id)):
        row_cells = cells_by_row.get(row.id, {})
        values = [{"column_id": cid, "value": row_cells.get(cid, "")} for cid in col_ids]
        rows_out.append(
            {
                "id": row.id,
                "sort_order": row.sort_order,
                "label": row.label,
                "values": values,
            }
        )

    return {
        "tag": {"id": chart.tag_id, "name": chart.tag.name},
        "title": chart.title,
        "columns": columns,
        "rows": rows_out,
    }


class SizeChartByTagView(APIView):
    """
    GET /api/v1/size-charts/by-tag/?name=<tag name>

    Returns the active size chart for the tag (case-insensitive name match), or 404.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="name",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Tag name (unique, matched case-insensitively).",
            ),
        ],
        responses={200: SizeChartByTagSerializer},
    )
    def get(self, request):
        raw = request.query_params.get("name")
        if raw is None or not str(raw).strip():
            return Response(
                {"detail": "Query parameter 'name' is required."},
                status=400,
            )
        name = str(raw).strip()
        tag = Tag.objects.filter(name__iexact=name).first()
        if tag is None:
            return Response({"detail": "Not found."}, status=404)

        chart = (
            SizeChart.objects.filter(tag=tag, is_active=True)
            .select_related("tag")
            .prefetch_related(
                "rows",
                "columns",
                Prefetch(
                    "cells",
                    queryset=SizeChartCell.objects.select_related("row", "column"),
                ),
            )
            .first()
        )
        if chart is None:
            return Response({"detail": "Not found."}, status=404)

        return Response(_serialize_size_chart(chart))
