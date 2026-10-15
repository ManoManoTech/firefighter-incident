from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.incidents.enums import IncidentStatus
from firefighter.slack.models.conversation import Conversation, ConversationStatus
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_archive")
@app.event("group_archive")
def channel_archive(event: dict[str, Any]) -> None:
    logger.debug(event)
    channel_id = get_in(event, "channel")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(
        _status=ConversationStatus.ARCHIVED
    )

    # The bot archives the channel itself when an incident is closed: only archives made
    # by someone else, on a still-open incident, are out of the process.
    archiver_slack_id = get_in(event, "user")
    if not archiver_slack_id or archiver_slack_id == SlackApp().details["user_id"]:
        return
    incident_channel = (
        IncidentChannel.objects.filter(channel_id=channel_id)
        .select_related("incident")
        .first()
    )
    if incident_channel is None or incident_channel.incident.status >= IncidentStatus.CLOSED:
        return
    # Imported here: the task imports the Slack messages, which import the Slack views.
    from firefighter.slack.tasks.notify_out_of_process_archive import (
        notify_out_of_process_archive,
    )

    notify_out_of_process_archive.delay(incident_channel.incident.id, archiver_slack_id)
