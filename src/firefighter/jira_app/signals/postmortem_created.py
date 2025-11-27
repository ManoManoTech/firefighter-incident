from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django.apps import apps
from django.conf import settings
from django.dispatch.dispatcher import receiver

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
    from firefighter.jira_app.service_postmortem import (  # noqa: PLC0415
        jira_postmortem_service,
    )

    return jira_postmortem_service


def _get_confluence_postmortem_manager() -> type[PostMortemManager] | None:
    """Lazy import to avoid circular dependency with Confluence."""
    if not apps.is_installed("firefighter.confluence"):
        return None
    from firefighter.confluence.models import PostMortemManager  # noqa: PLC0415

    return PostMortemManager


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
    from firefighter.slack.tasks.reminder_postmortem import (  # noqa: PLC0415
        publish_fixed_next_actions,
        publish_postmortem_reminder,
    )

    logger.debug(f"Checking sender: sender={sender}, type={type(sender)}")
    if sender != "update_status":
        logger.debug(f"Ignoring signal from sender={sender}")
        return

    logger.debug("Sender is update_status, checking postmortem conditions")

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

    # Check and create Confluence post-mortem
    if enable_confluence:
        has_confluence = hasattr(incident, "postmortem_for")
        logger.debug(f"Confluence enabled, has_confluence={has_confluence}")
        if not has_confluence:
            confluence_manager = _get_confluence_postmortem_manager()
            if confluence_manager:
                logger.info(f"Creating Confluence post-mortem for incident #{incident.id}")
                try:
                    confluence_pm = confluence_manager._create_confluence_postmortem(  # noqa: SLF001
                        incident
                    )
                except Exception:
                    logger.exception(
                        f"Failed to create Confluence post-mortem for incident #{incident.id}"
                    )
        else:
            logger.debug(f"Confluence post-mortem already exists for incident #{incident.id}")

    # Check and create Jira post-mortem
    if enable_jira_postmortem:
        has_jira = hasattr(incident, "jira_postmortem_for")
        logger.debug(f"Jira post-mortem enabled, has_jira={has_jira}")
        if not has_jira:
            logger.info(f"Creating Jira post-mortem for incident #{incident.id}")
            try:
                jira_service = _get_jira_postmortem_service()
                jira_pm = jira_service.create_postmortem_for_incident(incident)
            except Exception:
                logger.exception(
                    f"Failed to create Jira post-mortem for incident #{incident.id}"
                )
        else:
            logger.debug(f"Jira post-mortem already exists for incident #{incident.id}")

    # Send signal if at least one post-mortem was created
    if confluence_pm or jira_pm:
        from firefighter.incidents.signals import postmortem_created  # noqa: PLC0415

        logger.info(
            f"Post-mortem(s) created for incident #{incident.id}: "
            f"confluence={confluence_pm is not None}, jira={jira_pm is not None}"
        )
        postmortem_created.send_robust(sender=__name__, incident=incident)

    # Publish reminder
    publish_postmortem_reminder(incident)
