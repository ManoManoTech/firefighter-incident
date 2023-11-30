from __future__ import annotations

import logging
from typing import Any

from firefighter.slack.models.conversation import Conversation
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_id_changed")
def channel_id_changed(event: dict[str, Any]) -> None:
    logger.debug(event)
    old_channel_id = event.get("old_channel_id")
    new_channel_id = event.get("new_channel_id")
    if not old_channel_id or not new_channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=old_channel_id).update(
        channel_id=new_channel_id
    )
