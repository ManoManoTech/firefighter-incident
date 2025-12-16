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
    """Close Jira incident ticket based on incident status and priority.

    Closure logic:
    - P1/P2 (needs_postmortem): Close only when incident is CLOSED
    - P3+ (no postmortem): Close when incident is MITIGATED or CLOSED
    - POST_MORTEM status never closes the ticket (it remains open during PM phase)
    """
    if "_status" not in updated_fields:
        return

    if not hasattr(incident, "jira_ticket") or incident.jira_ticket is None:
        logger.warning(
            f"Trying to close Jira ticket for incident {incident.id} but no Jira ticket found"
        )
        return

    # Determine if we should close the ticket based on status and priority
    should_close = False

    if incident_update.status == IncidentStatus.CLOSED:
        # Always close on CLOSED regardless of priority
        should_close = True
    elif incident_update.status == IncidentStatus.MITIGATED:
        # Only close on MITIGATED if incident doesn't need postmortem (P3+)
        should_close = not incident.needs_postmortem

    # POST_MORTEM status never closes the ticket - it stays open during PM phase

    if should_close:
        status_label = incident_update.status.label if incident_update.status else "Unknown"
        logger.info(f"Closing Jira ticket for incident {incident.id} (status: {status_label})")
        client.close_issue(issue_id=incident.jira_ticket.id)
        # XXX We may want to add a comment if there is an incident update message on close
