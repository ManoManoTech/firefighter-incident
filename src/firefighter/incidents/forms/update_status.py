from __future__ import annotations

from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.utils import EnumChoiceField, GroupedModelChoiceField
from firefighter.incidents.models import Component, Priority


class UpdateStatusForm(forms.Form):
    message = forms.CharField(
        label="Update message",
        widget=forms.Textarea,
        min_length=10,
        max_length=1200,
        required=False,
    )
    status = EnumChoiceField(
        enum_class=IncidentStatus,
        label="Status",
        choices=IncidentStatus.choices_lt(IncidentStatus.CLOSED),
    )
    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_update=True),
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
