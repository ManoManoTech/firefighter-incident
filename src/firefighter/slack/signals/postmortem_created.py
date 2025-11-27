from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver
from slack_sdk.errors import SlackApiError

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
    # Refresh incident from database to get the newly created post-mortem relationships
    # This is necessary because the signal might be sent before the ORM cache is updated
    try:
        incident.refresh_from_db()
    except Exception:
        logger.exception(f"Failed to refresh incident #{incident.id} from database")
        return

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

    # Update the initial incident message with post-mortem links
    from firefighter.slack.messages.slack_messages import (  # noqa: PLC0415
        SlackMessageIncidentDeclaredAnnouncement,
    )

    incident.conversation.send_message_and_save(
        SlackMessageIncidentDeclaredAnnouncement(incident)
    )

    # Add bookmarks for each available post-mortem
    if has_confluence:
        try:
            incident.conversation.add_bookmark(
                title="Postmortem (Confluence)",
                link=incident.postmortem_for.page_url,
                emoji=":confluence:",
            )
        except SlackApiError as e:
            logger.warning(
                f"Failed to add Confluence bookmark for incident #{incident.id}: {e}. "
                "This is expected in test environments without custom emojis."
            )

    if has_jira:
        try:
            incident.conversation.add_bookmark(
                title=f"Postmortem ({incident.jira_postmortem_for.jira_issue_key})",
                link=incident.jira_postmortem_for.issue_url,
                emoji=":jira_new:",
            )
        except SlackApiError as e:
            logger.warning(
                f"Failed to add Jira bookmark for incident #{incident.id}: {e}. "
                "This is expected in test environments without custom emojis."
            )
