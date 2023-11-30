from __future__ import annotations

from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firefighter.incidents"
    label = "incidents"

    def ready(self) -> None:
        from firefighter.incidents import tasks
        from firefighter.incidents.models.incident_update import set_event_ts
