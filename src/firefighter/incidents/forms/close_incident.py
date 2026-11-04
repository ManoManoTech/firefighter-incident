from __future__ import annotations

from typing import Any

from django import forms

from firefighter.incidents.forms.origin import OriginFieldsMixin
from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import IncidentCategory


class CloseIncidentForm(OriginFieldsMixin):
    title = forms.CharField(
        label="Title",
        max_length=128,
        min_length=10,
        widget=forms.TextInput,
    )
    description = forms.CharField(
        label="Summary",
        widget=forms.Textarea,
        min_length=10,
        max_length=1200,
    )
    message = forms.CharField(
        label="Update message",
        widget=forms.Textarea,
        min_length=10,
        max_length=1200,
        required=False,
    )
    incident_category = GroupedModelChoiceField(
        choices_groupby="group",
        label="Incident category",
        queryset=IncidentCategory.objects.all()
        .select_related("group")
        .order_by(
            "group__order",
            "name",
        ),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Pre-filled from the incident (see the close modal's initial values): closing
        # confirms the origin recorded at mitigation, and lets it be corrected.
        self.add_origin_fields(incident=None)

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        self.clean_origin_fields()
        return cleaned_data
