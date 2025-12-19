"""Rules for publishing incidents in channels.

This module may be removed in a future version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from firefighter.incidents.enums import IncidentStatus

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate
    from firefighter.incidents.models.priority import Priority


def should_publish_in_general_channel(
    incident: Incident,
    incident_update: IncidentUpdate | None,
    *,
    old_priority: Priority | None = None,
) -> bool:
    # Only if incident is SEV[1-3], in PRD and not private
    if (
        incident.priority
        and incident.priority.value <= 3
        and incident.environment
        and incident.environment.value == "PRD"
        and not incident.private
    ):
        # If it has just been Mitigated
        if (
            incident.status == IncidentStatus.MITIGATED
            and incident_update is not None
            and incident_update.status is not None
        ):
            return True
        # If it has just been opened
        if incident.status == IncidentStatus.OPEN:
            return True
        # If it has been escalated from SEV[4-5] to SEV[1-3]
        if old_priority is not None and old_priority.value > 3:
            return True
    return False


def should_publish_in_it_deploy_channel(incident: Incident) -> bool:
    return (
        incident.environment.value == "PRD"
        and incident.priority.value <= 1
        and not incident.private
        and incident.incident_category.deploy_warning
    )


def should_publish_pm_in_general_channel(incident: Incident) -> bool:
    """Determine if post-mortem creation should be announced in #critical-incidents.

    Post-mortems are announced for P1-P3 production incidents that are not private
    and require a post-mortem.

    Args:
        incident: The incident for which a post-mortem was created.

    Returns:
        True if the post-mortem creation should be announced in tech_incidents channel.
    """
    return (
        incident.priority is not None
        and incident.priority.value <= 3
        and incident.environment is not None
        and incident.environment.value == "PRD"
        and not incident.private
        and incident.needs_postmortem
    )
