from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from celery import shared_task
from slack_sdk.errors import SlackApiError

from firefighter.raid.client import client as jira_client
from firefighter.raid.messages import (
    SlackMessageRaidDailyQualifierPrivate,
    SlackMessageRaidDailyQualifierPublic,
)
from firefighter.raid.service import get_current_qualifier
from firefighter.slack.models.conversation import Conversation

if TYPE_CHECKING:
    from firefighter.raid.models import JiraUser
logger = logging.getLogger(__name__)


def _daily_qualifier_message() -> None:
    """Sends a message in Slack with the daily qualifier both in public and private."""
    # Get daily qualifier
    qualifier: JiraUser = get_current_qualifier()
    if not qualifier:
        logger.warning("Qualifier not found for today.")
        return

    # Send message to public channel
    message_public = SlackMessageRaidDailyQualifierPublic(qualifier)
    qualifier_conversation = Conversation.objects.get_or_none(tag="qualification")
    if qualifier_conversation:
        try:
            qualifier_conversation.send_message_and_save(message_public)
        except SlackApiError:
            logger.exception(
                f"Couldn't send message to the channel {qualifier_conversation} for the user {qualifier.user}"
            )

    # Send private message to the qualifier
    message_private = SlackMessageRaidDailyQualifierPrivate()
    try:
        if qualifier.id:
            qualifier_jira_user = jira_client.get_jira_user_from_jira_id(qualifier.id)
            if qualifier_jira_user.user.slack_user is None:
                logger.warning(
                    f"Couldn't find Slack account ID for the qualifier {qualifier}"
                )
                return
            qualifier_jira_user.user.slack_user.send_private_message(
                message_private,
                unfurl_links=False,
            )
    except SlackApiError:
        logger.exception(
            f"Couldn't send private message to the qualifier {qualifier.user.slack_user}"
        )


@shared_task(name="raid._daily_qualifier_message")
def send_daily_qualifier_message() -> None:
    """Send a message with the daily qualifier.

    Ignore qualifiers that are not in the JiraUser table.
    """
    _daily_qualifier_message()
