"""Signal receiver: trigger Atlas Bot incident analysis on channel creation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch import receiver

from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.slack.models.incident_channel import IncidentChannel

logger = logging.getLogger(__name__)

# Gate: P1 (value=1), P2 (value=2), and P3 (value=3) trigger automated analysis.
_MAX_PRIORITY_VALUE = 3


@receiver(signal=incident_channel_done)
def trigger_atlas_incident_analysis(
    sender: Any,
    incident: Incident,
    channel: IncidentChannel,
    **kwargs: Any,
) -> None:
    """Enqueue an Atlas Bot incident analysis for P1/P2/P3 incidents.

    Connected to the ``incident_channel_done`` signal, which fires after the
    incident Slack channel has been fully set up (members invited, topic set,
    announcement posted).  Lower-priority incidents (P4-P5) are ignored.

    The actual HTTP call to Atlas is deferred to a Celery task so that any
    network latency or transient failure does not block the signal chain.
    """
    if incident.priority.value > _MAX_PRIORITY_VALUE:
        return

    logger.info(
        "Scheduling Atlas incident analysis for %s (priority %s, channel %s)",
        incident.canonical_name,
        incident.priority.name,
        channel.channel_id,
    )

    from firefighter.atlas.tasks.request_analysis import request_incident_analysis

    try:
        request_incident_analysis.delay(incident.id, channel.channel_id)
    except Exception:
        logger.exception(
            "Failed to enqueue Atlas analysis — incident channel creation unaffected",
            extra={"incident_id": incident.id},
        )
