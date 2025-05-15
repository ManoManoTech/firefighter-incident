from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from celery import chain, group, shared_task
from django.conf import settings
from django.utils import timezone

from firefighter.firefighter.filters import readable_time_delta
from firefighter.firefighter.utils import is_during_office_hours
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.slack.models import IncidentChannel
from firefighter.slack.models.user import SlackUser
from firefighter.slack.tasks.send_message import send_message

if TYPE_CHECKING:
    from slack_sdk.web.slack_response import SlackResponse

if settings.ENABLE_SLACK:
    from firefighter.slack.messages.slack_messages import (
        SlackMessageIncidentUpdateReminder,
    )
    from firefighter.slack.models import Message

logger = logging.getLogger(__name__)


@shared_task(
    name="slack.slack_save_reminder_message",
    retry_kwargs={"max_retries": 5},
    default_retry_delay=30,
)
def slack_save_reminder_message(
    message_response_data: SlackResponse, *args: int, **_kwargs: Any
) -> bool:
    """Save the [firefighter.slack.models.Message][] from a Slack response. First `args` is an [firefighter.incidents.models.Incident][] ID.

    Args:
        message_response_data (dict): SlackResponse data.
        *args: Expect one value, the [firefighter.incidents.models.Incident][] ID.
        **_kwargs: Ignored.
    """
    user = SlackUser.objects.get_user_by_slack_id(
        slack_id=message_response_data["message"]["user"]
    )
    conversation = IncidentChannel.objects.get(
        channel_id=message_response_data["channel"]
    )
    ts = datetime.fromtimestamp(
        float(message_response_data["message"]["ts"]), tz=timezone.utc  # type: ignore [attr-defined]
    )
    if user is None or not hasattr(user, "slack_user") or user.slack_user is None:
        msg = f"User not found for slack_id {message_response_data['message']['user']}"
        raise ValueError(msg)
    Message(
        conversation=conversation,
        ts=ts,
        type=message_response_data["message"]["type"],
        ff_type=message_response_data["message"]["metadata"]["event_type"],
        user=user.slack_user,
        incident_id=args[0],
    ).save()
    return True


@shared_task(name="slack.send_reminders")
def send_reminders() -> None:
    # Skip if it's out of office hours
    if not is_during_office_hours(timezone.localtime()):
        return
    # Get all incidents that have reminders (not Gameday, not resolved) and are not ignored
    opened_incidents = Incident.objects.filter(
        _status__lt=IncidentStatus.POST_MORTEM.value,
        priority__value__lte=5,
        ignore=False,
    ).select_related("conversation")

    list_fn = []

    for incident in opened_incidents:
        try:
            latest_update = incident.incidentupdate_set.latest("created_at")
        except IncidentUpdate.DoesNotExist:
            logger.warning("Incident %s has no updates", incident)
            continue
        if not hasattr(incident, "conversation"):
            logger.warning("Incident %s has no conversation", incident)
            continue
        if latest_update and latest_update.created_at:
            delta = timezone.now() - latest_update.created_at
            if delta <= incident.priority.reminder_time:
                continue

            # XXX Should check when the last reminder has been sent

            if Message.objects.filter(
                ff_type=SlackMessageIncidentUpdateReminder.id, incident=incident
            ).exists():
                continue

            # Craft the message
            time_delta_fmt = readable_time_delta(delta=delta)
            message_kwargs = SlackMessageIncidentUpdateReminder(
                incident=incident, time_delta_fmt=time_delta_fmt
            ).get_slack_message_params(blocks_as_dict=True)
            list_fn.append(
                chain(
                    send_message.s(
                        channel=incident.conversation.channel_id, **message_kwargs
                    ),
                    slack_save_reminder_message.s(incident.id),
                )
            )
    group(list_fn).apply_async()
