from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver

from firefighter.incidents.signals import incident_closed

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
logger = logging.getLogger(__name__)


@receiver(signal=incident_closed)
# pylint: disable=unused-argument
def incident_closed_slack(sender: Any, incident: Incident, **kwargs: Any) -> bool:
    if not hasattr(incident, "conversation"):
        logger.error(f"No Slack conversation to archive for incident {incident}.")
        return False
    return incident.conversation.archive_channel()
    # TODO Retry
