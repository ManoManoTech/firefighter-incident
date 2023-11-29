from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PagerdutyConfig(AppConfig):
    name = "pagerduty"

    def ready(self) -> None:
        import pagerduty.signals
        from pagerduty.tasks.fetch_services import fetch_services
        from pagerduty.tasks.trigger_oncall import trigger_oncall
