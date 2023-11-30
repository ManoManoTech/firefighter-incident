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
    if not hasattr(incident, "postmortem_for"):
        logger.warning(f"No PostMortem to post for incident {incident}.")
        return

    if not hasattr(incident, "conversation"):
        logger.warning(
            f"No Incident Slack channel to post PostMortem for incident {incident}."
        )
        return
    incident.conversation.send_message_and_save(
        SlackMessageIncidentPostMortemCreated(incident), pin=True
    )
    incident.conversation.add_bookmark(
        title="Postmortem", link=incident.postmortem_for.page_url, emoji=":confluence:"
    )
