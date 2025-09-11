from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import Environment, IncidentCategory, Priority
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import create_incident_conversation

if TYPE_CHECKING:
    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.user import User


def initial_environments() -> Environment:
    return Environment.objects.get(default=True)


def initial_priority() -> Priority:
    return Priority.objects.get(default=True)


class CreateIncidentFormBase(forms.Form):
    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


class CreateIncidentForm(CreateIncidentFormBase):
    title = forms.CharField(
        label="Title",
        max_length=128,
        min_length=10,
        widget=forms.TextInput(attrs={"placeholder": "What's going on?"}),
    )
    description = forms.CharField(
        label="Summary",
        widget=forms.Textarea(
            attrs={
                "placeholder": "Help people responding to the incident. This will be posted to #tech-incidents and on our internal status page.\nThis description can be edited later."
            }
        ),
        min_length=10,
        max_length=1200,
    )

    incident_category = GroupedModelChoiceField(
        choices_groupby="group",
        label="Incident category",
        queryset=(
            IncidentCategory.objects.all()
            .select_related("group")
            .order_by(
                "group__order",
                "name",
            )
        ),
    )
    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_create=True),
        initial=initial_priority,
    )
    environment = forms.ModelChoiceField(
        label="Environment",
        queryset=Environment.objects.all(),
        initial=initial_environments,
    )

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        incident = Incident.objects.declare(created_by=creator, **self.cleaned_data)
        impacts_form = SelectImpactForm(impacts_data)

        impacts_form.save(incident=incident)
        create_incident_conversation.send(
            "create_incident_form",
            incident=incident,
        )
