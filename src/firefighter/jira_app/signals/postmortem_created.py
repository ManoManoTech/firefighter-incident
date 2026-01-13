from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, Never

from django.apps import apps
from django.conf import settings
from django.dispatch.dispatcher import receiver
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.signals import incident_updated

if TYPE_CHECKING:
    from firefighter.confluence.models import PostMortemManager
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate
    from firefighter.jira_app.service_postmortem import JiraPostMortemService

logger = logging.getLogger(__name__)


def _get_jira_postmortem_service() -> JiraPostMortemService:
    """Lazy import to avoid circular dependency."""
    module = importlib.import_module("firefighter.jira_app.service_postmortem")
    return module.jira_postmortem_service


def _get_confluence_postmortem_manager() -> type[PostMortemManager] | None:
    """Lazy import to avoid circular dependency with Confluence."""
    if not apps.is_installed("firefighter.confluence"):
        return None
    module = importlib.import_module("firefighter.confluence.models")
    return module.PostMortemManager


def _update_mitigated_at_timestamp(
    incident: Incident, incident_update: IncidentUpdate, updated_fields: list[str]
) -> None:
    """Update mitigated_at timestamp when incident status changes to MITIGATED."""
    if (
        "_status" in updated_fields
        and incident_update.status == IncidentStatus.MITIGATED
        and incident.mitigated_at is None
    ):
        incident.mitigated_at = timezone.now()
        incident.save(update_fields=["mitigated_at"])
        logger.info(f"Set mitigated_at timestamp for incident #{incident.id}")


def _create_confluence_postmortem(incident: Incident) -> Any | None:
    """Create Confluence post-mortem if needed."""
    has_confluence = hasattr(incident, "postmortem_for")
    logger.debug(f"Confluence enabled, has_confluence={has_confluence}")

    if has_confluence:
        logger.debug(f"Confluence post-mortem already exists for incident #{incident.id}")
        return None

    confluence_manager = _get_confluence_postmortem_manager()
    if not confluence_manager:
        return None

    logger.info(f"Creating Confluence post-mortem for incident #{incident.id}")
    try:
        # Use the public API specifically for Confluence creation
        return confluence_manager.create_confluence_postmortem(incident)
    except Exception:
        logger.exception(
            f"Failed to create Confluence post-mortem for incident #{incident.id}"
        )
        return None


def _create_jira_postmortem(incident: Incident) -> Any | None:
    """Create Jira post-mortem if needed."""
    has_jira = hasattr(incident, "jira_postmortem_for")
    logger.debug(f"Jira post-mortem enabled, has_jira={has_jira}")

    if has_jira:
        logger.debug(f"Jira post-mortem already exists for incident #{incident.id}")
        return None

    logger.info(f"Creating Jira post-mortem for incident #{incident.id}")
    try:
        jira_service = _get_jira_postmortem_service()
        return jira_service.create_postmortem_for_incident(incident)
    except Exception:
        logger.exception(
            f"Failed to create Jira post-mortem for incident #{incident.id}"
        )
        return None


def _publish_postmortem_announcement(incident: Incident) -> None:
    """Publish post-mortem creation announcement to #critical-incidents."""
    # Dynamic imports to avoid circular dependencies
    slack_messages = importlib.import_module("firefighter.slack.messages.slack_messages")
    slack_models = importlib.import_module("firefighter.slack.models.conversation")
    slack_rules = importlib.import_module("firefighter.slack.rules")

    announcement_class = slack_messages.SlackMessageIncidentPostMortemCreatedAnnouncement
    conversation_class = slack_models.Conversation
    should_publish_pm_in_general_channel = slack_rules.should_publish_pm_in_general_channel

    if not should_publish_pm_in_general_channel(incident):
        return

    tech_incidents_conversation = conversation_class.objects.get_or_none(
        tag="tech_incidents"
    )
    if tech_incidents_conversation:
        announcement = announcement_class(incident)
        tech_incidents_conversation.send_message_and_save(announcement)
        logger.info(
            f"Post-mortem creation announced in tech_incidents for incident #{incident.id}"
        )
    else:
        logger.warning(
            "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
        )


@receiver(signal=incident_updated)
def postmortem_created_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Never,
) -> None:
    """Handle post-mortem creation when incident reaches MITIGATED status.

    This handler is registered in jira_app to ensure it works independently
    of Confluence being enabled. It creates post-mortems for both Confluence
    and Jira based on their respective feature flags.
    """
    logger.debug(
        f"postmortem_created_handler called with sender={sender}, "
        f"incident_id={incident.id}, status={incident_update.status}, "
        f"updated_fields={updated_fields}"
    )

    if not apps.is_installed("firefighter.slack"):
        logger.error("Slack app is not installed. Skipping.")
        return

    # Import Slack tasks after apps are loaded
    slack_tasks = importlib.import_module("firefighter.slack.tasks.reminder_postmortem")
    publish_fixed_next_actions = slack_tasks.publish_fixed_next_actions
    publish_postmortem_reminder = slack_tasks.publish_postmortem_reminder

    logger.debug(f"Checking sender: sender={sender}, type={type(sender)}")
    if sender != "update_status":
        logger.debug(f"Ignoring signal from sender={sender}")
        return

    logger.debug("Sender is update_status, checking postmortem conditions")

    # Update mitigated_at timestamp
    _update_mitigated_at_timestamp(incident, incident_update, updated_fields)

    # Check if we should create post-mortem(s)
    if (
        "_status" not in updated_fields
        or incident_update.status
        not in {IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM}
        or not incident.needs_postmortem
    ):
        logger.debug(
            f"Not creating post-mortem: _status in fields={('_status' in updated_fields)}, "
            f"status={incident_update.status}, needs_postmortem={incident.needs_postmortem}"
        )
        # For P3+ incidents, publish next actions reminder
        if (
            "_status" in updated_fields
            and incident_update.status
            in {IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM}
            and not incident.needs_postmortem
        ):
            publish_fixed_next_actions(incident)
        return

    logger.info(
        f"Creating post-mortem(s) for incident #{incident.id} "
        f"(status={incident_update.status}, needs_postmortem={incident.needs_postmortem})"
    )

    enable_confluence = getattr(settings, "ENABLE_CONFLUENCE", False)
    enable_jira_postmortem = getattr(settings, "ENABLE_JIRA_POSTMORTEM", False)

    confluence_pm = None
    jira_pm = None

    # Create Confluence post-mortem if enabled
    if enable_confluence:
        confluence_pm = _create_confluence_postmortem(incident)

    # Create Jira post-mortem if enabled
    if enable_jira_postmortem:
        jira_pm = _create_jira_postmortem(incident)

    # Send signal and announcements if at least one post-mortem was created
    if confluence_pm or jira_pm:
        signals_module = importlib.import_module("firefighter.incidents.signals")
        postmortem_created = signals_module.postmortem_created

        logger.info(
            f"Post-mortem(s) created for incident #{incident.id}: "
            f"confluence={confluence_pm is not None}, jira={jira_pm is not None}"
        )
        postmortem_created.send_robust(sender=__name__, incident=incident)
        _publish_postmortem_announcement(incident)

    # Publish reminder
    publish_postmortem_reminder(incident)
