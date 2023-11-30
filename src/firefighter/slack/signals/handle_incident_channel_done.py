from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django.conf import settings
from django.dispatch.dispatcher import receiver

from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentComProcess,
    SlackMessageIncidentRolesUpdated,
)
from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.slack.models.incident_channel import IncidentChannel

logger = logging.getLogger(__name__)
SLACK_APP_EMOJI: str = settings.SLACK_APP_EMOJI


# noinspection PyUnusedLocal
@receiver(signal=incident_channel_done)
def incident_channel_done_bookmarks(
    incident: Incident, channel: IncidentChannel, **kwargs: Any
) -> None:
    channel.add_bookmark(
        title="Incident Page",
        link=incident.status_page_url
        + "?utm_medium=FireFighter+Slack&utm_source=Slack+Bookmark&utm_campaign=Bookmark+In+Channel",
        emoji=SLACK_APP_EMOJI,
    )


# noinspection PyUnusedLocal
@receiver(incident_channel_done)
def sev1_process_reminder(
    incident: Incident, channel: IncidentChannel, **kwargs: Never
) -> None:
    if incident.priority.value == 1 and incident.environment.value == "PRD":
        channel.send_message_and_save(SlackMessageIncidentComProcess(incident))


@receiver(incident_channel_done)
def send_roles_message_in_conversation(
    incident: Incident, channel: IncidentChannel, **kwargs: Any
) -> None:
    update_roles_message = SlackMessageIncidentRolesUpdated(
        incident=incident,
        incident_update=None,
        first_update=True,
    )
    incident.conversation.send_message_and_save(update_roles_message)
