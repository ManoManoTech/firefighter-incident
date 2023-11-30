from __future__ import annotations

from django.urls import path

from firefighter.pagerduty.views.oncall_list import OncallListView
from firefighter.pagerduty.views.oncall_trigger import CreatePagerDutyIncidentFreeView

app_name = "pagerduty"
urlpatterns = [
    path("oncall/", OncallListView.as_view(), name="oncall-list"),
    path(
        "oncall/trigger/",
        CreatePagerDutyIncidentFreeView.as_view(),
        name="oncall_trigger",
    ),
]
