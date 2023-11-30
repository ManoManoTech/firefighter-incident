from __future__ import annotations

from django import forms

from firefighter.slack.models.sos import Sos


class SosForm(forms.Form):
    sos = forms.ModelChoiceField(
        queryset=Sos.objects.all(), empty_label=None, required=True, label="SOS"
    )
