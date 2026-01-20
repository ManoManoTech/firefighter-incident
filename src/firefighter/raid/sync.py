"""Synchronization utilities for bidirectional sync between Impact, Jira and Slack."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from django.core.cache import cache
from django.db import transaction

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models import (
    Incident,
    IncidentRole,
    IncidentRoleType,
    IncidentUpdate,
    Priority,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.client import client as jira_client
from firefighter.raid.models import JiraTicket

logger = logging.getLogger(__name__)

# Cache timeout for sync operations (in seconds)
SYNC_CACHE_TIMEOUT = 30


class SyncDirection(Enum):
    """Direction of synchronization."""

    IMPACT_TO_JIRA = "impact_to_jira"
    JIRA_TO_IMPACT = "jira_to_impact"
    IMPACT_TO_SLACK = "impact_to_slack"
    SLACK_TO_IMPACT = "slack_to_impact"


# Bidirectional status mapping between Jira and Impact
JIRA_TO_IMPACT_STATUS_MAP = {
    "Open": IncidentStatus.INVESTIGATING,
    "To Do": IncidentStatus.INVESTIGATING,
    "In Progress": IncidentStatus.FIXING,
    "In Review": IncidentStatus.FIXING,
    "Resolved": IncidentStatus.FIXED,
    "Done": IncidentStatus.FIXED,
    "Closed": IncidentStatus.POST_MORTEM,
    "Reopened": IncidentStatus.INVESTIGATING,
    "Blocked": IncidentStatus.FIXING,
    "Waiting": IncidentStatus.FIXING,
}

IMPACT_TO_JIRA_STATUS_MAP = {
    IncidentStatus.OPEN: "Open",
    IncidentStatus.INVESTIGATING: "In Progress",
    IncidentStatus.FIXING: "In Progress",
    IncidentStatus.FIXED: "Resolved",
    IncidentStatus.POST_MORTEM: "Closed",
    IncidentStatus.CLOSED: "Closed",
}

# Priority mapping between Jira (string) and Impact (numeric)
JIRA_TO_IMPACT_PRIORITY_MAP = {
    "Highest": 1,  # P1 - Critical
    "High": 2,  # P2 - High
    "Medium": 3,  # P3 - Medium
    "Low": 4,  # P4 - Low
    "Lowest": 5,  # P5 - Lowest
}


def should_skip_sync(
    entity_type: str, entity_id: str | int, direction: SyncDirection
) -> bool:
    """Check if we should skip this sync to prevent loops.

    Uses a cache-based approach to track recent syncs and prevent infinite loops.

    Args:
        entity_type: Type of entity being synced (e.g., 'incident', 'jira_ticket')
        entity_id: ID of the entity
        direction: Direction of sync

    Returns:
        True if sync should be skipped, False otherwise
    """
    cache_key = f"sync:{entity_type}:{entity_id}:{direction.value}"

    # Check if this sync was recently performed
    if cache.get(cache_key):
        logger.debug(f"Skipping sync for {cache_key} - recent sync detected")
        return True

    # Mark this sync as in progress
    cache.set(cache_key, value=True, timeout=SYNC_CACHE_TIMEOUT)
    return False


def sync_jira_status_to_incident(jira_ticket: JiraTicket, jira_status: str) -> bool:
    """Sync Jira status to Impact incident status.

    Args:
        jira_ticket: The JiraTicket model instance
        jira_status: The new Jira status string

    Returns:
        True if sync was successful, False otherwise
    """
    if not jira_ticket.incident:
        logger.warning(
            f"JiraTicket {jira_ticket.key} has no linked incident - skipping status sync"
        )
        return False

    incident = jira_ticket.incident

    # Check for sync loop
    if should_skip_sync("incident", incident.id, SyncDirection.JIRA_TO_IMPACT):
        return False

    # Map Jira status to Impact status
    impact_status = JIRA_TO_IMPACT_STATUS_MAP.get(jira_status)
    if not impact_status:
        logger.warning(f"Unknown Jira status: {jira_status} - skipping sync")
        return False

    # Check if status actually changed
    if incident.status == impact_status:
        logger.debug(
            f"Incident {incident.id} already has status {impact_status} - skipping"
        )
        return True

    try:
        with transaction.atomic():
            old_status = incident.status
            incident.status = impact_status
            incident.save(update_fields=["_status"])

            # Create an IncidentUpdate record
            IncidentUpdate.objects.create(
                incident=incident,
                _status=impact_status,
                created_by=None,  # System update
                message=f"Status updated from Jira: {jira_status}",
            )

            logger.info(
                f"Synced Jira status '{jira_status}' to incident {incident.id} "
                f"(status: {old_status} → {impact_status})"
            )
            return True

    except Exception:
        logger.exception("Failed to sync Jira status to incident")
        return False


def sync_jira_priority_to_incident(
    jira_ticket: JiraTicket, jira_priority: str
) -> bool:
    """Sync Jira priority to Impact incident priority.

    Args:
        jira_ticket: The JiraTicket model instance
        jira_priority: The new Jira priority string (e.g., 'High', 'Critical')

    Returns:
        True if sync was successful, False otherwise
    """
    if not jira_ticket.incident:
        logger.warning(
            f"JiraTicket {jira_ticket.key} has no linked incident - skipping priority sync"
        )
        return False

    incident = jira_ticket.incident

    # Check for sync loop
    if should_skip_sync("incident", incident.id, SyncDirection.JIRA_TO_IMPACT):
        return False

    # Map Jira priority to Impact priority value
    priority_value = JIRA_TO_IMPACT_PRIORITY_MAP.get(jira_priority)
    if not priority_value:
        logger.warning(f"Unknown Jira priority: {jira_priority} - skipping sync")
        return False

    try:
        # Get or create the Priority object
        priority = Priority.objects.get(value=priority_value)

        # Check if priority actually changed
        if incident.priority == priority:
            logger.debug(
                f"Incident {incident.id} already has priority {priority} - skipping"
            )
            return True

        with transaction.atomic():
            old_priority = incident.priority
            incident.priority = priority
            incident.save(update_fields=["priority"])

            # Create an IncidentUpdate record
            IncidentUpdate.objects.create(
                incident=incident,
                priority=priority,
                created_by=None,  # System update
                message=f"Priority updated from Jira: {jira_priority}",
            )

            logger.info(
                f"Synced Jira priority '{jira_priority}' to incident {incident.id} "
                f"(priority: {old_priority} → {priority})"
            )
            return True

    except Priority.DoesNotExist:
        logger.exception(f"Priority with value {priority_value} does not exist")
        return False
    except Exception:
        logger.exception("Failed to sync Jira priority to incident")
        return False


def _sync_assignee_to_commander(
    incident: Incident, assignee_data: dict[str, Any] | None
) -> None:
    """Sync Jira assignee to incident commander role."""
    if not assignee_data:
        return

    assignee_id = assignee_data.get("accountId")
    if not assignee_id:
        return

    try:
        jira_user = JiraUser.objects.get(id=assignee_id)
        # Get or create commander role
        commander_role_type = IncidentRoleType.objects.filter(
            slug="commander"
        ).first()
        if commander_role_type:
            # Update or create commander role for this incident
            IncidentRole.objects.update_or_create(
                incident=incident,
                role_type=commander_role_type,
                defaults={"user": jira_user.user},
            )
    except JiraUser.DoesNotExist:
        logger.warning(f"JiraUser with id {assignee_id} not found")


def sync_jira_fields_to_incident(
    jira_ticket: JiraTicket, jira_fields: dict[str, Any]
) -> bool:
    """Sync various Jira fields to Impact incident.

    Args:
        jira_ticket: The JiraTicket model instance
        jira_fields: Dictionary of Jira fields that changed

    Returns:
        True if all syncs were successful, False if any failed
    """
    if not jira_ticket.incident:
        logger.warning(
            f"JiraTicket {jira_ticket.key} has no linked incident - skipping field sync"
        )
        return False

    incident = jira_ticket.incident
    success = True
    updated_fields = []

    # Check for sync loop
    if should_skip_sync("incident", incident.id, SyncDirection.JIRA_TO_IMPACT):
        return False

    try:
        with transaction.atomic():
            # Sync summary/title
            if "summary" in jira_fields and jira_fields["summary"] != incident.title:
                incident.title = jira_fields["summary"]
                updated_fields.append("title")

            # Sync description
            if (
                "description" in jira_fields
                and jira_fields["description"] != incident.description
            ):
                incident.description = jira_fields["description"]
                updated_fields.append("description")

            # Sync assignee to incident commander role
            if "assignee" in jira_fields:
                _sync_assignee_to_commander(incident, jira_fields.get("assignee"))

            if updated_fields:
                incident.save(update_fields=updated_fields)

                # Create an IncidentUpdate record
                IncidentUpdate.objects.create(
                    incident=incident,
                    created_by=None,  # System update
                    message=f"Fields updated from Jira: {', '.join(updated_fields)}",
                )

                logger.info(
                    f"Synced Jira fields to incident {incident.id}: {updated_fields}"
                )

    except Exception:
        logger.exception("Failed to sync Jira fields to incident")
        success = False

    return success


def _build_jira_update_fields(incident: Incident, updated_fields: list[str]) -> dict[str, Any]:
    """Build the update fields dictionary for Jira based on incident changes."""
    update_fields: dict[str, Any] = {}

    # Map Impact fields to Jira fields
    if "title" in updated_fields:
        update_fields["summary"] = incident.title

    if "description" in updated_fields:
        update_fields["description"] = incident.description

    if "priority" in updated_fields and incident.priority:
        # Map numeric priority to Jira priority string
        priority_map_reverse = {v: k for k, v in JIRA_TO_IMPACT_PRIORITY_MAP.items()}
        jira_priority = priority_map_reverse.get(incident.priority.value)
        if jira_priority:
            update_fields["priority"] = {"name": jira_priority}

    return update_fields


def _sync_commander_to_jira(incident: Incident) -> dict[str, Any] | None:
    """Get Jira assignee field for incident commander."""
    try:
        commander_role_type = IncidentRoleType.objects.filter(slug="commander").first()
        if commander_role_type:
            commander_role = IncidentRole.objects.filter(
                incident=incident, role_type=commander_role_type
            ).first()
            if commander_role and commander_role.user:
                jira_user = jira_client.get_jira_user_from_user(commander_role.user)
                return {"assignee": {"accountId": jira_user.id}}
    except (AttributeError, ValueError) as e:
        logger.warning(f"Could not find Jira user for commander: {e}")
    return None


def sync_incident_to_jira(incident: Incident, updated_fields: list[str]) -> bool:
    """Sync Impact incident changes to Jira ticket.

    Args:
        incident: The Incident model instance
        updated_fields: List of field names that were updated

    Returns:
        True if sync was successful, False otherwise
    """
    try:
        # Get the linked Jira ticket
        jira_ticket = JiraTicket.objects.get(incident=incident)
    except JiraTicket.DoesNotExist:
        logger.debug(f"Incident {incident.id} has no linked Jira ticket - skipping")
        return False

    # Check for sync loop
    if should_skip_sync("jira_ticket", jira_ticket.id, SyncDirection.IMPACT_TO_JIRA):
        return False

    try:
        # Build basic field updates
        update_fields = _build_jira_update_fields(incident, updated_fields)

        # Handle status separately (uses transitions, not field updates)
        if "status" in updated_fields:
            jira_status = IMPACT_TO_JIRA_STATUS_MAP.get(incident.status)
            if jira_status and jira_client.transition_issue(jira_ticket.key, jira_status):
                logger.info(
                    f"Transitioned Jira ticket {jira_ticket.key} to status: {jira_status}"
                )

        # Handle commander assignment
        if "commander" in updated_fields:
            commander_fields = _sync_commander_to_jira(incident)
            if commander_fields:
                update_fields.update(commander_fields)

        # Apply field updates if any
        if update_fields and jira_client.update_issue(jira_ticket.key, update_fields):
            logger.info(
                f"Synced incident {incident.id} to Jira ticket {jira_ticket.key}: "
                f"{list(update_fields.keys())}"
            )

    except Exception:
        logger.exception("Failed to sync incident to Jira")
        return False
    else:
        return True


def handle_jira_webhook_update(
    issue_data: dict[str, Any], changelog_data: dict[str, Any]
) -> bool:
    """Handle incoming Jira webhook update and sync to Impact.

    Args:
        issue_data: The Jira issue data from webhook
        changelog_data: The changelog data showing what changed

    Returns:
        True if sync was successful, False otherwise
    """
    jira_key = issue_data.get("key")
    if not jira_key:
        logger.error("No Jira key in webhook data")
        return False

    try:
        jira_ticket = JiraTicket.objects.get(key=jira_key)
    except JiraTicket.DoesNotExist:
        logger.warning(f"JiraTicket with key {jira_key} not found - skipping sync")
        return False

    # Process each changed field
    success = True
    for item in changelog_data.get("items", []):
        field_name = item.get("field")
        new_value = item.get("toString")

        if field_name == "status":
            if not sync_jira_status_to_incident(jira_ticket, new_value):
                success = False

        elif field_name == "priority":
            if not sync_jira_priority_to_incident(jira_ticket, new_value):
                success = False

        elif field_name in {"summary", "description", "assignee"}:
            # Get the full issue fields for these updates
            fields = issue_data.get("fields", {})
            jira_fields = {
                "summary": fields.get("summary"),
                "description": fields.get("description"),
                "assignee": fields.get("assignee"),
            }
            if not sync_jira_fields_to_incident(jira_ticket, jira_fields):
                success = False

    return success
