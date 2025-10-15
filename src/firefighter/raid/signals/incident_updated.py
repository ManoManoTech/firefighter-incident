from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.signals import incident_updated
from firefighter.raid.client import client

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate

logger = logging.getLogger(__name__)


@receiver(signal=incident_updated, sender="update_status")
def incident_updated_close_ticket_when_mitigated_or_postmortem(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    # Close Jira ticket if mitigated, postmortem, or closed
    if "_status" in updated_fields and incident_update.status in {
        IncidentStatus.MITIGATED,
        IncidentStatus.POST_MORTEM,
        IncidentStatus.CLOSED,
    }:
        if not hasattr(incident, "jira_ticket") or incident.jira_ticket is None:
            logger.warning(
                f"Trying to close Jira ticket for incident {incident.id} but not having"
            )
            return
        client.close_issue(issue_id=incident.jira_ticket.id)
        # XXX We may want to add a comment if there is an incident update message on close
