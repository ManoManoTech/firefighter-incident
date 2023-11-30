from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RaidConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "raid"
    name = "firefighter.raid"
    verbose_name = "RAID"

    def ready(self) -> None:
        import firefighter.raid.tasks
        import firefighter.raid.urls
        from firefighter.raid.signals import (
            incident_created,
            incident_updated,
            update_qualifiers_rotation,
        )

        return super().ready()
