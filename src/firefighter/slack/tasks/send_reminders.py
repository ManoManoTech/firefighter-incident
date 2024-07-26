from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from celery import chain, group, shared_task
from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from firefighter.firefighter.filters import readable_time_delta
from firefighter.firefighter.utils import is_during_office_hours
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.slack.messages.slack_messages import (
    SlackMessageChannelReminderPostMortem,
    SlackMessageIncidentUpdateReminderCommander,
)
from firefighter.slack.models import IncidentChannel
from firefighter.slack.models.user import SlackUser
from firefighter.slack.tasks.reminder_postmortem import (
    send_reminder,
)
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
        float(message_response_data["message"]["ts"]), tz=timezone.utc
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
                logger.debug("Ignored task")
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


@shared_task(name="slack.send_postmortem_late_reminder")
def send_postmortem_late_reminder() -> None:
    """Sends reminder messages for incidents requiring postmortem updates.

      - For each incident, it checks:
    a. If a reminder to the commander was sent more than two days ago and no channel message exists, sends a new reminder to the incident's channel.
    b. If no reminder has ever been sent to the commander and the last incident update was over two days ago, sends a direct reminder to the commander.
    """
    # Skip if it's out of office hours
    if not is_during_office_hours(timezone.localtime()):
        logger.debug("out of office hours")
        return
    # Get all incidents that have reminders (not Gameday, not resolved) and are not ignored
    opened_incidents = (
        Incident.objects.filter(
            _status__gte=IncidentStatus.FIXED.value,
            _status__lt=IncidentStatus.CLOSED.value,
            priority__value__lte=5,
            ignore=False,
        )
        .select_related("conversation")
        .prefetch_related(
            Prefetch(
                "roles_set",
                queryset=IncidentRole.objects.all()
                .order_by("id")
                .select_related("role_type", "user", "user__slack_user")
                .filter(role_type__slug="commander_roles"),
                to_attr="commander",
            ),
        )
    )

    for incident in opened_incidents:
        latest_update = None
        try:
            latest_update = IncidentUpdate.objects.filter(incident=incident).latest(
                "updated_at"
            )
        except IncidentUpdate.DoesNotExist:
            logger.exception(f"No update found for incident: {incident.id}")
            continue

        existing_messages_commander = (
            (
                Message.objects.filter(
                    ff_type=SlackMessageIncidentUpdateReminderCommander.id,
                    incident=incident,
                    ts__gte=latest_update.updated_at - timedelta(days=2),
                )
            )
            .select_related("conversation")
            .order_by("-ts")
            .first()
        )

        existing_messages_channel = (
            (
                Message.objects.filter(
                    ff_type=SlackMessageChannelReminderPostMortem.id,
                    incident=incident,
                )
            )
            .select_related("conversation")
            .exists()
        )

        time_since_update = timezone.now() - latest_update.updated_at
        commander_roles = incident.roles_set.all()

        if existing_messages_commander:
            time_since_last_commander_message = (
                timezone.now() - existing_messages_commander.ts
            )
            if (
                time_since_last_commander_message >= timedelta(days=3)
                and not existing_messages_channel
            ):
                send_reminder(
                    incident=incident, commander_role=commander_roles, to_channel=True
                )

        if not existing_messages_commander and time_since_update >= timedelta(days=3):
            send_reminder(
                incident=incident, commander_role=commander_roles, to_channel=False
            )
