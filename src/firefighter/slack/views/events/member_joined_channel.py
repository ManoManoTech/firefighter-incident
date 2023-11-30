from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.models import SlackUser
from firefighter.slack.models.conversation import Conversation, ConversationType
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("member_joined_channel")
def member_joined_channel(event: dict[str, Any]) -> None:
    """When a user joins a channel, we add it to the list of conversations.

    API Reference: https://api.slack.com/events/member_joined_channel
    """
    logger.debug(event)
    channel_id = get_in(event, "channel")
    channel_type = get_in(event, "channel_type")
    user_id = get_in(event, "user")
    inviter = get_in(event, "inviter")
    if not channel_id:
        logger.warning(f"Invalid event! {event}")
        return

    conversation = Conversation.objects.get_or_none(channel_id=channel_id)
    if not conversation:
        logger.warning(f"Conversation {channel_id} does not exist!")
        return

    if channel_type == "C" and conversation.type != ConversationType.PUBLIC_CHANNEL:
        conversation.type = ConversationType.PUBLIC_CHANNEL
        conversation.save()
    elif channel_type == "G" and conversation.type != ConversationType.PRIVATE_CHANNEL:
        conversation.type = ConversationType.PRIVATE_CHANNEL
        conversation.save()
    if user_id:
        user = SlackUser.objects.get_user_by_slack_id(slack_id=user_id)
        if user is None:
            logger.warning(f"User {user_id} does not exist!")
            return
        conversation.members.add(user)

        # Check if Conversation is also IncidentChannel
        try:
            incident_channel: IncidentChannel = conversation.incidentchannel
        except IncidentChannel.DoesNotExist:
            return

        if inviter and incident_channel:
            inviter_user = SlackUser.objects.get_user_by_slack_id(slack_id=inviter)
            if inviter_user is None:
                logger.warning(f"Inviter {inviter} does not exist!")
                return

            logger.debug(f"User {user.id} joined {conversation} by {inviter_user.id}")

        else:
            inviter_user = None

        incident_channel.members.add(user)
