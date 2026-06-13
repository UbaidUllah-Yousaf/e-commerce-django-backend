from django.core.exceptions import ValidationError
from django.db import models

from ecommerce.models.tag import Tag
from utils.timestamped import TimeStampedModel


class SizeChart(TimeStampedModel):
    """One size grid per tag (e.g. all products tagged "T-Shirts" share one chart)."""

    tag = models.OneToOneField(
        Tag,
        on_delete=models.CASCADE,
        related_name="size_chart",
    )
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Size chart for {self.tag.name}"


class SizeChartRow(TimeStampedModel):
    chart = models.ForeignKey(
        SizeChart,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    sort_order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chart", "sort_order"],
                name="size_chart_row_unique_chart_sort",
            ),
        ]

    def __str__(self):
        return f"{self.chart_id} {self.label}"


class SizeChartColumn(TimeStampedModel):
    chart = models.ForeignKey(
        SizeChart,
        on_delete=models.CASCADE,
        related_name="columns",
    )
    sort_order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chart", "sort_order"],
                name="size_chart_column_unique_chart_sort",
            ),
        ]

    def __str__(self):
        return f"{self.chart_id} {self.label}"


class SizeChartCell(TimeStampedModel):
    chart = models.ForeignKey(
        SizeChart,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    row = models.ForeignKey(
        SizeChartRow,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    column = models.ForeignKey(
        SizeChartColumn,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    value = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chart", "row", "column"],
                name="size_chart_cell_unique_chart_row_column",
            ),
        ]

    def clean(self):
        super().clean()
        if self.row_id and self.column_id and self.chart_id:
            if self.row.chart_id != self.chart_id or self.column.chart_id != self.chart_id:
                raise ValidationError("Row and column must belong to this chart.")
