from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from django.db.utils import IntegrityError
from slack_sdk.errors import SlackApiError

from firefighter.firefighter.utils import get_in
from firefighter.slack.models.message import Message
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_incident_context import get_incident_from_context

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

app = SlackApp()

logger = logging.getLogger(__name__)


def reaction_on_message_only(event: dict[str, Any]) -> bool:
    return bool(get_in(event, ["item", "type"]) == "message")


def special_reaction_only(event: dict[str, Any]) -> bool:
    return event.get("reaction") == "mega"


@app.event("reaction_added", matchers=[reaction_on_message_only, special_reaction_only])
def reaction_added(event: dict[str, Any], client: WebClient) -> None:
    logger.debug(event)

    # Check that the event is a message reaction with the right emoji
    item = event.get("item")
    if not isinstance(item, dict):
        err_msg = f"Event item is not a dict: {item}"
        raise TypeError(err_msg)

    # Get needed variables and assert they are here
    conversation_id = item.get("channel")
    message_ts = item.get("ts")
    if not isinstance(message_ts, str | float):
        err_msg = f"Event message_ts is not a str or float: {message_ts}"
        raise TypeError(err_msg)

    # The timestamp is UTC
    message_ts_dt = datetime.fromtimestamp(float(message_ts), tz=UTC)
    user_reaction = event.get("user")

    if not isinstance(conversation_id, str):
        err_msg = f"Event conversation_id is not a str: {conversation_id}"
        raise TypeError(err_msg)
    if not isinstance(user_reaction, str):
        err_msg = f"Event user_reaction is not a str: {user_reaction}"
        raise TypeError(err_msg)
    if not isinstance(message_ts, str):
        err_msg = f"Event message_ts is not a str: {message_ts_dt}"
        raise TypeError(err_msg)

    # Check that the message is in an incident conversation
    incident = get_incident_from_context(event)
    if not incident:
        return

    user = SlackUser.objects.get_user_by_slack_id(slack_id=user_reaction)
    if not user or not hasattr(user, "slack_user") or not user.slack_user:
        logger.error("User %s could not be found.", user_reaction)
        return

    # Get the message as it is not included in the event
    try:
        result = client.conversations_history(
            channel=conversation_id, inclusive=True, oldest=message_ts, limit=1
        )

    except SlackApiError:
        logger.exception("Could not get the message from reaction!")
        return

    messages = result.get("messages")
    if not isinstance(messages, list):
        err_msg = f"Event messages is not a list: {messages}"
        raise TypeError(err_msg)

    message = messages[0]
    message_text = message.get("text")
    logger.debug(message)
    if not isinstance(message_text, str):
        err_msg = f"Event message_text is not a str: {message_text}"
        raise TypeError(err_msg)

    try:
        message = Message(
            ts=message_ts_dt,
            text=message_text,
            type=message["type"],
            blocks=message.get("blocks"),
            conversation_id=incident.conversation.id,
            user_id=user.slack_user.id,
        )
        message.save()
    except IntegrityError:
        # We do not post in a thread as the client won't show it.
        client.chat_postEphemeral(
            channel=conversation_id,
            user=user_reaction,
            text=f"<@{user_reaction}> :x: An Incident Update has already been created from this message!",
        )
        return

    incident_update = incident.create_incident_update(
        message=message_text,
        created_by=user,
        event_ts=message_ts_dt,
    )
    message.incident_update = incident_update
    message.save()


@app.event("reaction_added")
def reaction_added_ignore() -> None:
    """Ignore other reaction_added events.
    Must be the last event handler for reaction_added.
    """
    return
