"""Signal handler for syncing incident updates to Jira."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from firefighter.incidents.models import Incident, IncidentUpdate
from firefighter.raid.sync import sync_incident_to_jira

if TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Incident)
def sync_incident_changes_to_jira(
    sender: type[Model], instance: Incident, *, created: bool, **kwargs: Any
) -> None:
    """Sync incident changes to the linked Jira ticket.

    Args:
        sender: The model class (Incident)
        instance: The incident instance that was saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments including update_fields
    """
    # Skip sync for new incidents (they're handled by the creation signal)
    if created:
        return

    # Check if RAID is enabled
    if not getattr(settings, "ENABLE_RAID", False):
        return

    # Get the list of updated fields
    update_fields = kwargs.get("update_fields")
    if not update_fields:
        # If no specific fields were updated, assume all fields
        # In practice, we should always use update_fields when saving
        logger.debug(
            f"No update_fields specified for incident {instance.id} save - skipping sync"
        )
        return

    # Fields that should trigger a sync to Jira
    sync_fields = {"title", "description", "priority", "status", "commander"}
    updated_sync_fields = list(set(update_fields) & sync_fields)

    if not updated_sync_fields:
        logger.debug(
            f"No syncable fields updated for incident {instance.id} - skipping sync"
        )
        return

    # Sync to Jira
    try:
        sync_success = sync_incident_to_jira(instance, updated_sync_fields)
        if sync_success:
            logger.info(
                f"Successfully synced incident {instance.id} to Jira "
                f"(fields: {updated_sync_fields})"
            )
        else:
            logger.warning(
                f"Failed to sync incident {instance.id} to Jira "
                f"(fields: {updated_sync_fields})"
            )
    except Exception:
        logger.exception(f"Error syncing incident {instance.id} to Jira")


@receiver(post_save, sender=IncidentUpdate)
def sync_incident_update_to_jira(
    sender: type[Model], instance: IncidentUpdate, *, created: bool, **kwargs: Any
) -> None:
    """Sync incident update changes to the linked Jira ticket.

    This handles IncidentUpdate records which track field-level changes.

    Args:
        sender: The model class (IncidentUpdate)
        instance: The incident update instance that was saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only process new updates
    if not created:
        return

    # Check if RAID is enabled
    if not getattr(settings, "ENABLE_RAID", False):
        return

    incident = instance.incident
    updated_fields = []

    # Check which fields were updated in this IncidentUpdate
    if instance.title and instance.title != incident.title:
        updated_fields.append("title")

    if instance.description and instance.description != incident.description:
        updated_fields.append("description")

    if instance.priority and instance.priority != incident.priority:
        updated_fields.append("priority")

    if instance.status and instance.status != incident.status:
        updated_fields.append("status")

    # Skip if this update was created by the sync process itself
    if instance.created_by is None and "from Jira" in (instance.message or ""):
        logger.debug(
            f"Skipping sync for IncidentUpdate {instance.id} - appears to be from Jira sync"
        )
        return

    if updated_fields:
        try:
            sync_success = sync_incident_to_jira(incident, updated_fields)
            if sync_success:
                logger.info(
                    f"Successfully synced IncidentUpdate {instance.id} to Jira "
                    f"(fields: {updated_fields})"
                )
            else:
                logger.warning(
                    f"Failed to sync IncidentUpdate {instance.id} to Jira "
                    f"(fields: {updated_fields})"
                )
        except Exception:
            logger.exception(f"Error syncing IncidentUpdate {instance.id} to Jira")
