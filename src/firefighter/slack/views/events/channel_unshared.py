from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("channel_unshared")
def channel_unshared(event: dict[str, Any]) -> None:
    logger.debug(event)
    channel_id = get_in(event, "channel")
    channel_is_ext_shared = get_in(event, "is_ext_shared")
    if not channel_id or channel_is_ext_shared is None:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(
        is_shared=channel_is_ext_shared
    )
