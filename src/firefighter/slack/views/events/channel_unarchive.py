from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.conversation import Conversation, ConversationStatus
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_unarchive")
@app.event("group_unarchive")
def channel_unarchive(event: dict[str, Any]) -> None:
    logger.debug(event)
    channel_id = get_in(event, "channel")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return
    # We explicitely make multiple calls for potential signals on Conversation model
    conversation = Conversation.objects.get_or_none(channel_id=channel_id)
    if conversation is None:
        return
    conversation.status = ConversationStatus.OPENED
    conversation.save()
    try:
        conversation.conversations_join()
    except Conversation.DoesNotExist:
        return
