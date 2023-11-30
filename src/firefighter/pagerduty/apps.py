from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PagerdutyConfig(AppConfig):
    name = "firefighter.pagerduty"
    labels = "pagerduty"

    def ready(self) -> None:
        import firefighter.pagerduty.signals
        from firefighter.pagerduty.tasks.fetch_services import fetch_services
        from firefighter.pagerduty.tasks.trigger_oncall import trigger_oncall
