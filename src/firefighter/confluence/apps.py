from __future__ import annotations

from django.apps import AppConfig


class ConfluenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "confluence"
    name = "firefighter.confluence"

    def ready(self) -> None:
        # Register signals
        # E.g. usage: create PostMortem page on incident_updated

        from firefighter.confluence import signals, tasks
