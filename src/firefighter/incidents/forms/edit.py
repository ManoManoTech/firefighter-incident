from __future__ import annotations

from django import forms

from firefighter.incidents.models import Environment


def initial_environments() -> Environment:
    return Environment.objects.get(default=True)


class EditMetaForm(forms.Form):
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
    environment = forms.ModelChoiceField(
        label="Environment",
        queryset=Environment.objects.all(),
        initial=initial_environments,
    )
