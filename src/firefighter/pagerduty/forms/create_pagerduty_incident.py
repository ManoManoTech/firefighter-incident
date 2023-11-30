from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms
from django.conf import settings

from firefighter.pagerduty.models import PagerDutyService

if TYPE_CHECKING:
    from django.db.models import QuerySet


class CreatePagerDutyIncidentFreeForm(forms.Form):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_service_queryset() -> QuerySet[PagerDutyService]:
        if settings.DEBUG:
            return PagerDutyService.objects.all().order_by("summary")
        return PagerDutyService.objects.filter(ignore=False).order_by("summary")

    title = forms.CharField(
        label="What's going on?",
        max_length=128,
        min_length=10,
        widget=forms.TextInput,
    )
    service = forms.ModelChoiceField(
        queryset=get_service_queryset(),
    )
    #  Assign to users / escalation policies

    urgency = forms.ChoiceField(choices=[("high", "High"), ("low", "Low")])  # TODO Enum
    details = forms.CharField(
        label="More details",
        widget=forms.Textarea(
            attrs={"rows": 5},
        ),
        min_length=10,
        max_length=1200,
    )
