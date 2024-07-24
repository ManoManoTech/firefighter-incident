from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from firefighter.slack.messages.base import SlackMessageStrategy
from firefighter.slack.messages.slack_messages import (
    SlackMessageChannelReminderPostMortem,
    SlackMessageIncidentFixedNextActions,
    SlackMessageIncidentPostMortemReminder,
    SlackMessageIncidentUpdateReminderCommander,
)
from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.incident import Incident


logger = logging.getLogger(__name__)


@slack_client
def publish_postmortem_reminder(
    incident: Incident,
    client: WebClient = DefaultWebClient,
) -> None:
    """XXX Should return a message object, not send it."""
    if not hasattr(incident, "postmortem_for"):
        logger.warning(
            "Trying to send PostMortem reminder for incident #%s with no PostMortem!",
            incident.id,
        )
        return

    if not (hasattr(incident, "conversation") and incident.conversation.channel_id):
        logger.warning(
            "No conversation to post PM reminder for incident {incident.id}."
        )
        return
    update_status_message = SlackMessageIncidentPostMortemReminder(incident)
    incident.conversation.send_message_and_save(
        update_status_message,
        client=client,
        strategy=SlackMessageStrategy.REPLACE,
        strategy_args={
            "replace": (
                SlackMessageIncidentFixedNextActions.id,
                SlackMessageIncidentPostMortemReminder.id,
            )
        },
    )


@slack_client
def publish_fixed_next_actions(
    incident: Incident,
    client: WebClient = DefaultWebClient,
) -> None:
    if not (hasattr(incident, "conversation") and incident.conversation.channel_id):
        logger.warning(
            "No conversation to post next actions for incident {incident.id}."
        )
        return
    update_status_message = SlackMessageIncidentFixedNextActions(incident)
    incident.conversation.send_message_and_save(
        update_status_message,
        strategy=SlackMessageStrategy.REPLACE,
        strategy_args={
            "replace": (
                SlackMessageIncidentFixedNextActions.id,
                SlackMessageIncidentPostMortemReminder.id,
            )
        },
        client=client,
    )


def send_reminder(incident: Incident, to_channel) -> None:
    prefetched_roles = getattr(incident, "roles_prefetched", [])
    if to_channel:
        # Send a message in the incident channel
        incident.conversation.send_message_and_save(
            SlackMessageChannelReminderPostMortem(incident)
        )
    else:
        # Send a private message to commander
        for role in prefetched_roles:
            user = role.user
            slack_user = user.slack_user
            if slack_user:
                private_message = SlackMessageIncidentUpdateReminderCommander(
                    incident=incident, time_delta_fmt=str(incident.created_at)
                )
                slack_user.send_private_message(private_message)
