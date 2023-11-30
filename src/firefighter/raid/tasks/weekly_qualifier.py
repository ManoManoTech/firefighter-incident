from __future__ import annotations

import datetime
import logging

from celery import shared_task
from slack_sdk.errors import SlackApiError

from firefighter.raid.messages import SlackMessageRaidWeeklyQualifiers
from firefighter.raid.models import QualifierRotation
from firefighter.raid.signals.update_qualifiers_rotation import (
    complete_qualifiers_rotation,
)
from firefighter.slack.models.conversation import Conversation

logger = logging.getLogger(__name__)


@shared_task(name="raid._weekly_qualifiers_message")
def send_weekly_qualifiers_message() -> None:
    """Send a message with the weekly qualifiers.

    Ignore qualifiers that are not in the JiraUser table.
    """
    _weekly_qualifiers_message()


def _weekly_qualifiers_message() -> None:
    """Sends a message in Slack with the weekly qualifiers rotation."""
    # Get weekly qualifiers in desired format
    today = datetime.datetime.now(tz=datetime.UTC).date()
    next_monday = today + datetime.timedelta(days=7 - today.weekday())
    qualifiers_weekly_rotation_queryset = (
        QualifierRotation.objects.filter(
            day__gte=next_monday,
            day__lte=next_monday + datetime.timedelta(days=4),
        )
        .order_by("day")
        .select_related("jira_user__user")
    )
    if (
        not qualifiers_weekly_rotation_queryset
        or qualifiers_weekly_rotation_queryset.count() < 5
    ):
        logger.warning("Next week qualifiers rotation is incomplete. Completing it...")
        try:
            complete_qualifiers_rotation()
        except QualifierRotation.DoesNotExist:
            logger.exception("Couldn't complete qualifier rotation.")
            return

    # Send message to public channel
    message_public = SlackMessageRaidWeeklyQualifiers(
        qualifiers_weekly_rotation_queryset
    )
    qualifier_conversation = Conversation.objects.get_or_none(tag="qualification")
    if qualifier_conversation:
        try:
            qualifier_conversation.send_message_and_save(message_public)
        except SlackApiError:
            logger.exception(
                f"Couldn't send message to channel {qualifier_conversation} with weekly qualifiers rotation."
            )
