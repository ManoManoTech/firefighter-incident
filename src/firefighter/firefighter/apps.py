from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class FireFighter(AppConfig):
    name = "firefighter.firefighter"
    label = "firefighter"
    verbose_name = "FireFighter"

    def ready(self) -> None:
        import firefighter.components
