from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django.apps import apps
from django.dispatch.dispatcher import receiver

from firefighter.incidents.signals import incident_updated

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate

logger = logging.getLogger(__name__)


@receiver(signal=incident_updated)
def incident_updated_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Never,
) -> None:
    """Handle Confluence-specific incident updates.

    Note: Post-mortem creation logic has been moved to jira_app.signals.postmortem_created
    to handle both Confluence and Jira post-mortems independently of Confluence being enabled.
    """
    if not apps.is_installed("firefighter.slack"):
        logger.error("Slack app is not installed. Skipping.")
        return

    # This handler is now empty but kept for future Confluence-specific logic
    # Post-mortem creation is handled by jira_app.signals.postmortem_created
