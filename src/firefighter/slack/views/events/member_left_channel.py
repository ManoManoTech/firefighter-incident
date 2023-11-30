from __future__ import annotations

import logging
from typing import Any

from firefighter.firefighter.utils import get_in
from firefighter.incidents.models.incident_membership import IncidentMembership
from firefighter.slack.models import SlackUser
from firefighter.slack.models.conversation import Conversation, ConversationType
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("member_left_channel")
def member_left_channel(event: dict[str, Any]) -> None:
    """When a user leaves a channel, we remove it from the list of conversations.

    API Reference: https://api.slack.com/events/member_left_channel
    """
    channel_id = get_in(event, "channel")
    channel_type = get_in(event, "channel_type")
    user_id = get_in(event, "user")
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
        conversation.members.remove(user)

        # Check if Conversation is also IncidentChannel
        try:
            incident_channel: IncidentChannel = conversation.incidentchannel
        except IncidentChannel.DoesNotExist:
            return
        if incident_channel:
            logger.info(f"User {user} left {conversation} ")

            incident = incident_channel.incident
            IncidentMembership.objects.filter(incident=incident, user=user).delete()
