from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AtlasConfig(AppConfig):
    """Django app that forwards P1/P2/P3 incident channel-creation events to Atlas Bot.

    When a high-severity incident channel is created in FireFighter, an
    ``incident_channel_done`` signal receiver (registered in ``ready()``) enqueues
    a Celery task that POSTs the incident context to the Atlas Bot trigger endpoint.
    Atlas then performs an automated root-cause analysis and posts the
    report directly into the incident Slack channel.

    Controlled by the ``ENABLE_ATLAS`` setting (default ``False``).
    """

    label = "atlas"
    name = "firefighter.atlas"

    def ready(self) -> None:
        # Register signal receivers and ensure the Celery task module is loaded.
        import firefighter.atlas.signals
        from firefighter.atlas.tasks import request_analysis
