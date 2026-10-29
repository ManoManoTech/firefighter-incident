from __future__ import annotations

from typing import Any

from django import forms

from firefighter.incidents.forms.origin import OriginFieldsMixin
from firefighter.incidents.models import Environment


def initial_environments() -> list[Environment]:
    """Get default environments for the form."""
    return list(Environment.objects.filter(default=True))


class EditMetaForm(OriginFieldsMixin):
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
    environment = forms.ModelMultipleChoiceField(
        label="Environment",
        queryset=Environment.objects.all(),
        initial=initial_environments,
        required=True,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # The origin is often known before mitigation (e.g. a provider outage)
        self.add_origin_fields(incident=None)

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        self.clean_origin_fields()
        return cleaned_data
