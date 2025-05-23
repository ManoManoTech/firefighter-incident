from __future__ import annotations

from django import forms

from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import Component


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
    component = GroupedModelChoiceField(
        choices_groupby="group",
        label="Issue category",
        queryset=Component.objects.all()
        .select_related("group")
        .order_by(
            "group__order",
            "name",
        ),
    )
