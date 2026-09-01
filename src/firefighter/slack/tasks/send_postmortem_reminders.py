"""Celery task reminding the Commander to drive a mitigated incident through to closure.

An incident that stays mitigated is not finished: P1/P2 still need their post-mortem, P3 still
needs its key events and its closure. This task nudges whoever holds command once the incident
has sat mitigated for its priority's `postmortem_reminder_time`, then again every
`postmortem_reminder_repeat_time` for as long as nothing moves. Both live on the Priority, next
to `reminder_time`, so they can be tuned per priority in the Django admin - including down to a
few minutes to rehearse the flow.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from django.db.models import DateTimeField, ExpressionWrapper, F, Q
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.rules import should_publish_pm_in_general_channel

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from firefighter.slack.models import Message

if settings.ENABLE_SLACK:
    from firefighter.slack.messages.slack_messages import (
        SlackMessageIncidentProcessReminder,
        SlackMessageIncidentProcessReminderAnnouncement,
    )
    from firefighter.slack.models import Message

logger = logging.getLogger(__name__)


def _last_reminder(incident: Incident) -> Message | None:
    return (
        Message.objects.filter(
            ff_type=SlackMessageIncidentProcessReminder.id,
            incident=incident,
        )
        .order_by("-ts")
        .first()
    )


def _last_progress_at(incident: Incident) -> datetime | None:
    """When the incident last moved: its latest update, or its mitigation."""
    latest_update = incident.incidentupdate_set.order_by("-created_at").first()
    candidates = [
        moment
        for moment in (
            incident.mitigated_at,
            latest_update.created_at if latest_update else None,
        )
        if moment is not None
    ]
    return max(candidates) if candidates else None


def _reminder_due(
    incident: Incident, now: datetime
) -> tuple[bool, timedelta | None, bool]:
    """Decide whether to remind, how long the process has been still, and if it is the first time.

    The queryset already selected incidents past their priority's `postmortem_reminder_time`, so
    this only arbitrates the repeats.

    Returns:
        (due, stale_for, is_first_reminder). `stale_for` is None on the first reminder, where
        the message already states how long the incident has been mitigated.
    """
    last_reminder = _last_reminder(incident)
    if last_reminder is None:
        return (True, None, True)

    repeat_delay = incident.priority.postmortem_reminder_repeat_time
    if not repeat_delay:
        return (False, None, False)

    last_progress_at = _last_progress_at(incident)
    # Anything more recent than the last reminder counts as movement and restarts the clock.
    quiet_since = max(
        moment for moment in (last_reminder.ts, last_progress_at) if moment is not None
    )
    stale_for = now - quiet_since
    return (stale_for >= repeat_delay, stale_for, False)


@shared_task(name="slack.send_postmortem_reminders")
def send_postmortem_reminders() -> None:
    """Remind the Commander of every stalled mitigated incident to drive it to closure.

    The Celery name is kept for compatibility: it is stored in the `PeriodicTask` row created by
    the `slack.0009` migration, and renaming it would leave Beat dispatching a task nobody
    registers.
    """
    now = timezone.now()

    # P1-P3 are the priorities that run the Slack incident process. GAMEDAY sits at value 20 but
    # requires a post-mortem, so it is matched on `needs_postmortem` rather than being dropped.
    # The reminder is due once mitigated_at + the priority's delay has passed, which Postgres
    # computes directly rather than us reading every mitigated incident back.
    incidents_needing_reminder = (
        Incident.objects.filter(
            Q(priority__value__lte=3) | Q(priority__needs_postmortem=True),
            mitigated_at__isnull=False,
            _status__in=[
                IncidentStatus.MITIGATED.value,
                IncidentStatus.POST_MORTEM.value,
            ],
            ignore=False,
        )
        .annotate(
            reminder_due_at=ExpressionWrapper(
                F("mitigated_at") + F("priority__postmortem_reminder_time"),
                output_field=DateTimeField(),
            )
        )
        .filter(reminder_due_at__lte=now)
        .select_related("conversation", "priority", "environment")
        .prefetch_related("roles_set__role_type", "roles_set__user__slack_user")
    )

    logger.info(
        f"Found {incidents_needing_reminder.count()} mitigated incidents past their reminder delay"
    )

    reminded = 0
    for incident in incidents_needing_reminder:
        # Skip if no conversation
        if not hasattr(incident, "conversation") or not incident.conversation:
            logger.warning(
                f"Incident #{incident.id} has no conversation, skipping reminder"
            )
            continue

        due, stale_for, is_first_reminder = _reminder_due(incident, now)
        if not due:
            logger.debug(
                f"Skipping incident #{incident.id} - reminded recently or the process moved"
            )
            continue

        # Send reminder to incident channel
        try:
            reminder_message = SlackMessageIncidentProcessReminder(
                incident, stale_for=stale_for
            )
            incident.conversation.send_message_and_save(reminder_message)
            reminded += 1
            logger.info(f"Sent process reminder to incident #{incident.id} channel")
            if _last_reminder(incident) is None:
                # The cadence is anchored on the saved Message. If saving silently failed (an
                # unknown bot SlackUser makes `create_from_slack_response` return None), every
                # run would remind again, so make that loud rather than mysterious.
                logger.error(
                    f"Process reminder for incident #{incident.id} was sent but not saved: "
                    "the repeat cadence cannot be tracked and reminders will be resent"
                )
        except Exception:
            logger.exception(
                f"Failed to send process reminder to incident #{incident.id} channel"
            )
            continue

        # Announce in #critical-incidents on the first reminder only: the repeats are a
        # conversation with the Commander, not a broadcast.
        if is_first_reminder and should_publish_pm_in_general_channel(incident):
            try:
                tech_incidents_conversation = Conversation.objects.get_or_none(
                    tag="tech_incidents"
                )
                if tech_incidents_conversation:
                    announcement = SlackMessageIncidentProcessReminderAnnouncement(
                        incident
                    )
                    tech_incidents_conversation.send_message_and_save(announcement)
                    logger.info(
                        f"Sent process reminder to tech_incidents for incident #{incident.id}"
                    )
                else:
                    logger.warning(
                        "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
                    )
            except Exception:
                logger.exception(
                    f"Failed to send process reminder to tech_incidents for incident #{incident.id}"
                )

    logger.info(f"Process reminder task completed. Sent {reminded} reminder(s).")
