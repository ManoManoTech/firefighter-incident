from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver

from firefighter.incidents.signals import postmortem_created
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentPostMortemCreated,
)

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)


@receiver(signal=postmortem_created)
# pylint: disable=unused-argument
def postmortem_created_send(sender: Any, incident: Incident, **kwargs: Any) -> None:
    # Check if at least one post-mortem exists
    has_confluence = hasattr(incident, "postmortem_for")
    has_jira = hasattr(incident, "jira_postmortem_for")

    if not has_confluence and not has_jira:
        logger.warning(f"No PostMortem to post for incident {incident}.")
        return

    if not hasattr(incident, "conversation"):
        logger.warning(
            f"No Incident Slack channel to post PostMortem for incident {incident}."
        )
        return

    # Send message with all available post-mortem links (pinned)
    incident.conversation.send_message_and_save(
        SlackMessageIncidentPostMortemCreated(incident), pin=True
    )

    # Add bookmarks for each available post-mortem
    if has_confluence:
        incident.conversation.add_bookmark(
            title="Postmortem (Confluence)",
            link=incident.postmortem_for.page_url,
            emoji=":confluence:",
        )

    if has_jira:
        incident.conversation.add_bookmark(
            title=f"Postmortem ({incident.jira_postmortem_for.jira_issue_key})",
            link=incident.jira_postmortem_for.issue_url,
            emoji=":jira:",
        )
