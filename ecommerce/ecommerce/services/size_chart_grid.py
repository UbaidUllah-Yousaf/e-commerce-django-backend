"""
Serialize / deserialize size chart grids for the admin spreadsheet editor.

Grid payload shape::

    {
        "column_labels": ["CHEST", "WAIST", "HIP"],
        "rows": [
            {"label": "S", "values": ["23", "32", "36"]},
            {"label": "M", "values": ["25", "", ""]}
        ]
    }
"""

from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from ecommerce.models.size_chart import SizeChart, SizeChartCell, SizeChartColumn, SizeChartRow

MAX_COLUMNS = 40
MAX_ROWS = 100


def chart_to_grid_dict(chart: SizeChart) -> dict[str, Any]:
    columns = sorted(chart.columns.all(), key=lambda c: (c.sort_order, c.id))
    rows = sorted(chart.rows.all(), key=lambda r: (r.sort_order, r.id))
    cells: dict[tuple[int, int], str] = {}
    for cell in chart.cells.all():
        cells[(cell.row_id, cell.column_id)] = cell.value

    column_labels = [c.label for c in columns]
    row_payload = []
    for row in rows:
        values = [cells.get((row.id, col.id), "") for col in columns]
        row_payload.append({"label": row.label, "values": values})

    return {"column_labels": column_labels, "rows": row_payload}


def chart_to_grid_json(chart: SizeChart) -> str:
    return json.dumps(chart_to_grid_dict(chart))


def validate_grid_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Grid must be a JSON object.")
    cols = data.get("column_labels")
    rows = data.get("rows")
    if cols is None or rows is None:
        raise ValueError("Grid requires column_labels and rows.")
    if not isinstance(cols, list) or not isinstance(rows, list):
        raise ValueError("column_labels and rows must be arrays.")
    if len(cols) > MAX_COLUMNS or len(rows) > MAX_ROWS:
        raise ValueError(f"At most {MAX_COLUMNS} columns and {MAX_ROWS} rows.")
    col_count = len(cols)
    for i, label in enumerate(cols):
        if not isinstance(label, str) or len(label.strip()) > 255:
            raise ValueError(f"Invalid column label at index {i}.")
    normalized_cols = [str(c).strip() for c in cols]
    normalized_rows = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Row {i} must be an object.")
        label = row.get("label", "")
        if not isinstance(label, str) or len(label.strip()) > 255:
            raise ValueError(f"Invalid row label at index {i}.")
        values = row.get("values", [])
        if not isinstance(values, list):
            raise ValueError(f"Row {i} values must be an array.")
        if len(values) != col_count:
            raise ValueError(
                f"Row {i} must have exactly {col_count} value(s) (one per column)."
            )
        norm_vals = []
        for v in values:
            if v is None:
                norm_vals.append("")
            elif not isinstance(v, str):
                norm_vals.append(str(v))
            else:
                if len(v) > 255:
                    raise ValueError("Cell value too long (max 255 characters).")
                norm_vals.append(v)
        normalized_rows.append({"label": str(label).strip(), "values": norm_vals})
    return {"column_labels": normalized_cols, "rows": normalized_rows}


@transaction.atomic
def apply_grid_payload_to_chart(chart: SizeChart, data: dict[str, Any]) -> None:
    """Replace all rows, columns, and cells for this chart."""
    payload = validate_grid_payload(data)
    column_labels = payload["column_labels"]
    rows_payload = payload["rows"]

    SizeChartCell.objects.filter(chart=chart).delete()
    SizeChartRow.objects.filter(chart=chart).delete()
    SizeChartColumn.objects.filter(chart=chart).delete()

    SizeChartColumn.objects.filter(chart=chart).delete()

    if column_labels:
        SizeChartColumn.objects.bulk_create(
            [
                SizeChartColumn(chart=chart, sort_order=i, label=label or f"Column {i + 1}")
                for i, label in enumerate(column_labels)
            ]
        )
    col_models = list(chart.columns.order_by("sort_order", "id"))

    if rows_payload:
        SizeChartRow.objects.bulk_create(
            [
                SizeChartRow(chart=chart, sort_order=i, label=row["label"] or f"Row {i + 1}")
                for i, row in enumerate(rows_payload)
            ]
        )
    row_models = list(chart.rows.order_by("sort_order", "id"))

    cells_to_create = []
    for ri, row in enumerate(row_models):
        vals = rows_payload[ri]["values"] if ri < len(rows_payload) else []
        for ci, col in enumerate(col_models):
            val = vals[ci] if ci < len(vals) else ""
            if val == "":
                continue
            cells_to_create.append(
                SizeChartCell(chart=chart, row=row, column=col, value=val)
            )
    if cells_to_create:
        SizeChartCell.objects.bulk_create(cells_to_create)
