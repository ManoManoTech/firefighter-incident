from __future__ import annotations

import logging
from typing import Any

from firefighter.utils import get_in
from slack.models.conversation import Conversation
from slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_shared")
def channel_shared(event: dict[str, Any]) -> None:
    logger.debug(event)
    channel_id = get_in(event, "channel")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(is_shared=True)
