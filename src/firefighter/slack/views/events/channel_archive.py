from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.conversation import Conversation, ConversationStatus
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
