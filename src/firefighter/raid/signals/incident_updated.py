from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.signals import incident_updated
from firefighter.raid.client import RAID_JIRA_WORKFLOW_NAME, client

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate

logger = logging.getLogger(__name__)
IMPACT_TO_JIRA_STATUS_MAP: dict[IncidentStatus, str] = {
    IncidentStatus.OPEN: "Incoming",
    IncidentStatus.INVESTIGATING: "in progress",
    IncidentStatus.MITIGATING: "in progress",
    IncidentStatus.MITIGATED: "Reporter validation",
    IncidentStatus.POST_MORTEM: "Reporter validation",
    IncidentStatus.CLOSED: "Closed",
}


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
    logger.warning(
        "incident_updated handler invoked for incident #%s with status %s; updated_fields=%s event_type=%s",
        getattr(incident, "id", "unknown"),
        incident_update.status,
        updated_fields,
        incident_update.event_type,
    )
    # Skip if this update was produced by Jira webhook sync to avoid redundant close calls
    if incident_update.event_type == "jira_status_sync":
        logger.debug(
            "Skipping Jira transition: incident #%s update came from Jira (event_type=jira_status_sync)",
            getattr(incident, "id", "unknown"),
        )
        return

    if "_status" not in updated_fields:
        logger.debug(
            "Skipping Jira transition: incident #%s update lacks _status in updated_fields (%s)",
            getattr(incident, "id", "unknown"),
            updated_fields,
        )
        return

    if not hasattr(incident, "jira_ticket") or incident.jira_ticket is None:
        logger.debug(
            f"Trying to close Jira ticket for incident {incident.id} but no Jira ticket found"
        )
        return

    # Special case: when Impact moves to MITIGATING, Jira must go through two steps:
    # "Pending resolution" then "in progress".
    if incident_update.status == IncidentStatus.MITIGATING:
        for step in ("Pending resolution", "in progress"):
            try:
                logger.debug(
                    "Transitioning Jira ticket %s via workflow %s to status %s (incident #%s, impact status %s)",
                    incident.jira_ticket.id,
                    RAID_JIRA_WORKFLOW_NAME,
                    step,
                    getattr(incident, "id", "unknown"),
                    incident_update.status,
                )
                client.transition_issue_auto(
                    incident.jira_ticket.id, step, RAID_JIRA_WORKFLOW_NAME
                )
            except Exception:
                logger.exception(
                    "Failed to transition Jira ticket %s to %s for incident %s",
                    incident.jira_ticket.id,
                    step,
                    incident.id,
                )
                return
        logger.info(
            "Transitioned Jira ticket %s through Pending resolution -> in progress from Impact status %s",
            incident.jira_ticket.id,
            incident_update.status.label if incident_update.status else "Unknown",
        )
        return

    # Decide target Jira status based on Impact status and postmortem requirement.
    # P3+ (no postmortem): close Jira when Impact reaches MITIGATED or CLOSED.
    # P1/P2 (needs_postmortem): close Jira only when Impact reaches CLOSED.
    target_jira_status: str | None = None
    if incident_update.status == IncidentStatus.CLOSED:
        target_jira_status = "Closed"
    else:
        target_jira_status = IMPACT_TO_JIRA_STATUS_MAP.get(incident_update.status)

    if target_jira_status is None:
        logger.info(
            "Skipping Jira transition: no Jira status mapping for Impact status %s (incident #%s)",
            incident_update.status,
            getattr(incident, "id", "unknown"),
        )
        return

    try:
        logger.debug(
            "Transitioning Jira ticket %s via workflow %s to status %s (incident #%s, impact status %s)",
            incident.jira_ticket.id,
            RAID_JIRA_WORKFLOW_NAME,
            target_jira_status,
            getattr(incident, "id", "unknown"),
            incident_update.status,
        )
        client.transition_issue_auto(
            incident.jira_ticket.id, target_jira_status, RAID_JIRA_WORKFLOW_NAME
        )
        logger.info(
            "Transitioned Jira ticket %s to %s from Impact status %s",
            incident.jira_ticket.id,
            target_jira_status,
            incident_update.status.label if incident_update.status else "Unknown",
        )
    except Exception:
        logger.exception(
            "Failed to transition Jira ticket %s to %s for incident %s",
            incident.jira_ticket.id,
            target_jira_status,
            incident.id,
        )
