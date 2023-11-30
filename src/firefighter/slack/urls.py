from __future__ import annotations

from django.urls import path

from firefighter.slack.views.views import SlackEventsHandler

app_name = "slack"
urlpatterns = [
    path("incident/", SlackEventsHandler.as_view(), name="slack_events_handler"),
]
