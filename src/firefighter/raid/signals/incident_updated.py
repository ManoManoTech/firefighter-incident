from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import incident_updated
from firefighter.raid.client import RAID_JIRA_WORKFLOW_NAME, client

if TYPE_CHECKING:
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


def _normalize_cache_value(value: Any) -> str:
    """Normalize cache values for loop-prevention keys."""
    if value is None:
        return ""
    # Lowercase strings for status consistency; leave numbers as stringified ints.
    if isinstance(value, str):
        return value.strip().lower()
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value).strip().lower()


def _set_impact_to_jira_cache(
    incident_id: Any, field: str, value: Any, timeout: int = 30
) -> None:
    cache_key = (
        f"sync:impact_to_jira:{incident_id}:{field}:{_normalize_cache_value(value)}"
    )
    cache.set(cache_key, True, timeout=timeout)


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
        _set_impact_to_jira_cache(incident.id, "status", target_jira_status)
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


# Listen to all incident_updated signals so both UI (update_status) and API/admin paths trigger
@receiver(signal=incident_updated)
def incident_updated_sync_priority_to_jira(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    """
    Push Impact priority changes to Jira custom priority field (customfield_11064).
    Skips if change originated from Jira (event_type='jira_priority_sync') to avoid loops.
    """
    logger.debug(
        "Priority sync handler invoked: incident #%s sender=%s updated_fields=%s event_type=%s",
        getattr(incident, "id", "unknown"),
        sender,
        updated_fields,
        incident_update.event_type,
    )

    if incident_update.event_type == "jira_priority_sync":
        logger.debug(
            "Skipping Jira priority sync: incident #%s update came from Jira (event_type=jira_priority_sync)",
            getattr(incident, "id", "unknown"),
        )
        return

    if "priority_id" not in updated_fields:
        logger.debug(
            "Skipping Jira priority sync: incident #%s update lacks priority_id in updated_fields (%s) sender=%s",
            getattr(incident, "id", "unknown"),
            updated_fields,
            sender,
        )
        return

    if not hasattr(incident, "jira_ticket") or incident.jira_ticket is None:
        logger.debug(
            "Skipping Jira priority sync: incident #%s has no Jira ticket",
            getattr(incident, "id", "unknown"),
        )
        return

    if not incident.priority:
        logger.debug(
            "Skipping Jira priority sync: incident #%s priority is missing",
            getattr(incident, "id", "unknown"),
        )
        return

    try:
        _set_impact_to_jira_cache(incident.id, "priority", incident.priority.value)
        client.update_issue_fields(
            incident.jira_ticket.id,
            customfield_11064={"value": str(incident.priority.value)},
        )
        logger.info(
            "Synced priority %s to Jira ticket %s (customfield_11064) for incident #%s",
            incident.priority.value,
            incident.jira_ticket.id,
            getattr(incident, "id", "unknown"),
        )
    except Exception:
        logger.exception(
            "Failed to sync priority %s to Jira ticket %s for incident %s",
            incident.priority.value,
            incident.jira_ticket.id,
            getattr(incident, "id", "unknown"),
        )


# Fallback: if an Incident save bypasses incident_updated (e.g., admin inline), push priority anyway.
@receiver(post_save, sender=Incident)
def incident_priority_post_save_fallback(
    sender: Any,
    instance: Incident,
    created: bool,
    update_fields: set[str] | None,
    **kwargs: Any,
) -> None:
    """
    Fallback to push priority to Jira when Incident saves with priority_id in update_fields
    but no incident_updated signal fired (e.g., admin edits). Skips when marked to avoid loops.
    """
    if created:
        return
    if update_fields and "priority_id" not in update_fields:
        return
    if getattr(instance, "_skip_priority_sync", False):
        logger.debug(
            "Skipping post_save priority sync for incident #%s due to skip flag",
            getattr(instance, "id", "unknown"),
        )
        return
    if not hasattr(instance, "jira_ticket") or instance.jira_ticket is None:
        logger.debug(
            "Skipping post_save priority sync: incident #%s has no Jira ticket",
            getattr(instance, "id", "unknown"),
        )
        return
    if not instance.priority:
        logger.debug(
            "Skipping post_save priority sync: incident #%s priority missing",
            getattr(instance, "id", "unknown"),
        )
        return

    try:
        _set_impact_to_jira_cache(instance.id, "priority", instance.priority.value)
        client.update_issue_fields(
            instance.jira_ticket.id,
            customfield_11064={"value": str(instance.priority.value)},
        )
        logger.info(
            "Post-save synced priority %s to Jira ticket %s (customfield_11064) for incident #%s",
            instance.priority.value,
            instance.jira_ticket.id,
            getattr(instance, "id", "unknown"),
        )
    except Exception:
        logger.exception(
            "Failed post-save priority sync %s to Jira ticket %s for incident %s",
            instance.priority.value,
            instance.jira_ticket.id,
            getattr(instance, "id", "unknown"),
        )


@receiver(post_save, sender=Incident)
def incident_status_post_save_fallback(
    sender: Any,
    instance: Incident,
    created: bool,
    update_fields: set[str] | None,
    **kwargs: Any,
) -> None:
    """
    Fallback to push status to Jira when Incident saves with status in update_fields
    but no incident_updated signal fired (e.g., admin edits). Skips when marked to avoid loops.
    """
    if created:
        return
    if (
        update_fields
        and "_status" not in update_fields
        and "status" not in update_fields
    ):
        return
    if getattr(instance, "_skip_status_sync", False):
        logger.debug(
            "Skipping post_save status sync for incident #%s due to skip flag",
            getattr(instance, "id", "unknown"),
        )
        return
    if not hasattr(instance, "jira_ticket") or instance.jira_ticket is None:
        logger.debug(
            "Skipping post_save status sync: incident #%s has no Jira ticket",
            getattr(instance, "id", "unknown"),
        )
        return
    target_jira_status = IMPACT_TO_JIRA_STATUS_MAP.get(instance.status)
    if target_jira_status is None:
        logger.debug(
            "Skipping post_save status sync: no Jira mapping for status %s (incident #%s)",
            instance.status,
            getattr(instance, "id", "unknown"),
        )
        return
    try:
        _set_impact_to_jira_cache(instance.id, "status", target_jira_status)
        client.transition_issue_auto(
            instance.jira_ticket.id, target_jira_status, RAID_JIRA_WORKFLOW_NAME
        )
        logger.info(
            "Post-save synced status %s to Jira ticket %s for incident #%s",
            instance.status,
            instance.jira_ticket.id,
            getattr(instance, "id", "unknown"),
        )
    except Exception:
        logger.exception(
            "Failed post-save status sync %s to Jira ticket %s for incident %s",
            instance.status,
            instance.jira_ticket.id,
            getattr(instance, "id", "unknown"),
        )
