"""Signal handlers for incident key events updates to sync with Jira post-mortem."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.dispatch import receiver
from django.template.loader import render_to_string

from firefighter.incidents.models.incident import Incident as IncidentModel
from firefighter.incidents.signals import incident_key_events_updated
from firefighter.jira_app.client import JiraClient
from firefighter.jira_app.service_postmortem import JiraPostMortemService

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)


@receiver(signal=incident_key_events_updated)
def sync_key_events_to_jira_postmortem(
    sender: Any, incident: Incident, **kwargs: dict[str, Any]
) -> None:
    """Update Jira post-mortem timeline when key events are updated.

    This handler is triggered when incident key events are updated via the web UI
    or Slack, and syncs the timeline to the associated Jira post-mortem ticket.

    Args:
        sender: The sender of the signal
        incident: The incident whose key events were updated
        **kwargs: Additional keyword arguments
    """
    # Check if Jira post-mortem is enabled
    if not getattr(settings, "ENABLE_JIRA_POSTMORTEM", False):
        logger.debug("Jira post-mortem disabled, skipping timeline sync")
        return

    # Check if incident has a Jira post-mortem
    if not hasattr(incident, "jira_postmortem_for") or not incident.jira_postmortem_for:
        logger.debug(f"Incident #{incident.id} has no Jira post-mortem, skipping timeline sync")
        return

    jira_postmortem = incident.jira_postmortem_for
    logger.info(
        f"Syncing key events timeline to Jira post-mortem {jira_postmortem.jira_issue_key} "
        f"for incident #{incident.id}"
    )

    try:
        # Prefetch incident updates for timeline generation
        incident_refreshed = (
            IncidentModel.objects.select_related("priority", "environment")
            .prefetch_related("incidentupdate_set")
            .get(pk=incident.pk)
        )

        # Generate updated timeline from template
        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"incident": incident_refreshed},
        )

        # Get the field ID for timeline from service
        service = JiraPostMortemService()
        timeline_field_id = service.field_ids.get("timeline")

        if not timeline_field_id:
            logger.error("Timeline field ID not found in Jira post-mortem service configuration")
            return

        # Update the Jira ticket
        client = JiraClient()
        issue = client.jira.issue(jira_postmortem.jira_issue_key)
        issue.update(fields={timeline_field_id: timeline_content})

        logger.info(
            f"Successfully updated timeline in Jira post-mortem {jira_postmortem.jira_issue_key}"
        )

    except Exception:
        logger.exception(
            f"Failed to update timeline in Jira post-mortem {jira_postmortem.jira_issue_key} "
            f"for incident #{incident.id}"
        )
