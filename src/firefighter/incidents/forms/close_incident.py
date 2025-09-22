from __future__ import annotations

from django import forms

from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import IncidentCategory


class CloseIncidentForm(forms.Form):
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
