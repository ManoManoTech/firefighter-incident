from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.conversation import Conversation, ConversationType
from firefighter.slack.slack_app import SlackApp

if TYPE_CHECKING:
    from slack_sdk.web import WebClient


app = SlackApp()

logger = logging.getLogger(__name__)


def only_channel_topic(event: dict[str, Any]) -> bool:
    return event.get("subtype") == "channel_topic"


def only_botuser(event: dict[str, Any]) -> bool:
    return event.get("user") == SlackApp().details["user_id"]


@app.event("message", matchers=[only_channel_topic, only_botuser])
def handle_message_events(event: dict[str, Any], client: WebClient) -> None:
    channel_id = event.get("channel")
    ts = event.get("ts")
    if not channel_id or not ts:
        err_msg = f"Missing channel_id or ts: {channel_id}, {ts}"
        raise ValueError(err_msg)
    if channel_id is None or ts is None:
        raise ValueError("channel_id or ts is None")
    client.chat_delete(channel=channel_id, ts=ts)


@app.event({"type": "message", "subtype": "channel_topic"})
def handle_message_events_ignore() -> None:
    """Ignore other message events.
    Must be the last event handler for message.
    """
    return


@app.event({"type": "message", "subtype": "channel_convert_to_private"})
def channel_convert_to_private(event: dict[str, Any]) -> None:
    channel_id = get_in(event, "channel")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(
        _type=ConversationType.PRIVATE_CHANNEL
    )


@app.event({"type": "message", "subtype": "channel_convert_to_public"})
def channel_convert_to_public(event: dict[str, Any]) -> None:
    channel_id = get_in(event, "channel")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    Conversation.objects.filter(channel_id=channel_id).update(
        _type=ConversationType.PUBLIC_CHANNEL
    )
