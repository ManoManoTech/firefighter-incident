from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_rename")
@app.event("group_rename")
def conversation_rename(event: dict[str, Any]) -> None:
    logger.debug(event)
    channel_id = get_in(event, "channel.id")
    channel_new_name = get_in(event, "channel.name")
    if not channel_id or not channel_new_name:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(name=channel_new_name)
