"""Warn when an incident channel is archived while the incident is still open.

Archiving a channel does not close the incident in IMPACT: the incident stays open with no
channel to post into, and the bot cannot unarchive it (Slack refuses `conversations.unarchive`
to bot tokens). The support channel is told, and so is whoever archived the channel.
"""

from __future__ import annotations

import logging

from celery import shared_task
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models.incident import Incident
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentChannelArchivedAlert,
    SlackMessageIncidentChannelArchivedDM,
)
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user import SlackUser

logger = logging.getLogger(__name__)


@shared_task(name="slack.notify_out_of_process_archive")
def notify_out_of_process_archive(incident_id: int, archiver_slack_id: str) -> None:
    incident = Incident.objects.get(pk=incident_id)

    support_conversation = Conversation.objects.get_or_none(tag="dev_firefighter")
    if support_conversation is None:
        logger.warning(
            "Could not find the dev_firefighter conversation to report the archived channel of incident #%s",
            incident.id,
        )
    else:
        try:
            support_conversation.send_message_and_save(
                SlackMessageIncidentChannelArchivedAlert(incident, archiver_slack_id)
            )
        except SlackApiError:
            logger.exception(
                "Could not report the archived channel of incident #%s", incident.id
            )

    archiver = SlackUser.objects.filter(slack_id=archiver_slack_id).first()
    if archiver is None:
        logger.info(
            "Archiver %s of incident #%s channel is unknown to IMPACT, no DM sent",
            archiver_slack_id,
            incident.id,
        )
        return
    try:
        archiver.send_private_message(SlackMessageIncidentChannelArchivedDM(incident))
    except SlackApiError:
        logger.exception(
            "Could not DM %s about the archived channel of incident #%s",
            archiver_slack_id,
            incident.id,
        )
