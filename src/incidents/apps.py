from __future__ import annotations

from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "incidents"

    def ready(self) -> None:
        from incidents import tasks
        from incidents.models.incident_update import set_event_ts
