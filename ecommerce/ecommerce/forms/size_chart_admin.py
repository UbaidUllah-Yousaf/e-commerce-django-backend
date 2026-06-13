import json

from django import forms
from django.core.exceptions import ValidationError

from ecommerce.models.size_chart import SizeChart
from ecommerce.services.size_chart_grid import chart_to_grid_json, validate_grid_payload

DEFAULT_GRID_JSON = json.dumps(
    {
        "column_labels": ["", "", ""],
        "rows": [
            {"label": "", "values": ["", "", ""]},
            {"label": "", "values": ["", "", ""]},
            {"label": "", "values": ["", "", ""]},
        ],
    }
)


class SizeChartAdminForm(forms.ModelForm):
    """Extra hidden field synced by the spreadsheet grid in the change form template."""

    grid_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        label="",
    )

    class Meta:
        model = SizeChart
        fields = ("tag", "title", "is_active", "grid_data")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["grid_data"].initial = chart_to_grid_json(self.instance)
        elif not self.data and not self.fields["grid_data"].initial:
            self.fields["grid_data"].initial = DEFAULT_GRID_JSON

    def clean_grid_data(self):
        raw = self.cleaned_data.get("grid_data")
        if raw is None or not str(raw).strip():
            return DEFAULT_GRID_JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid grid data (not valid JSON).") from exc
        try:
            normalized = validate_grid_payload(data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return json.dumps(normalized)
