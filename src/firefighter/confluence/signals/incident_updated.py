from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django.apps import apps
from django.dispatch.dispatcher import receiver

from firefighter.confluence.models import PostMortem
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.signals import incident_updated

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate

if apps.is_installed("firefighter.slack"):
    from firefighter.slack.tasks.reminder_postmortem import (
        publish_fixed_next_actions,
        publish_postmortem_reminder,
    )

logger = logging.getLogger(__name__)


@receiver(signal=incident_updated)
def incident_updated_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Never,
) -> None:
    if not apps.is_installed("firefighter.slack"):
        logger.error("Slack app is not installed. Skipping.")
        return
    if sender == "update_status":
        # Post postmortem reminder if needed
        if (
            "_status" in updated_fields
            and incident_update.status
            in {IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM}
            and incident.needs_postmortem
        ):
            if not hasattr(incident, "postmortem_for"):
                PostMortem.objects.create_postmortem_for_incident(incident)
            publish_postmortem_reminder(incident)
        elif (
            "_status" in updated_fields
            and incident_update.status
            in {IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM}
            and not incident.needs_postmortem
        ):
            publish_fixed_next_actions(incident)
