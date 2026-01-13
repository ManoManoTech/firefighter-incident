"""Celery task to send post-mortem reminders for incidents.

This task runs periodically to check for incidents that were mitigated
5 days ago and still need their post-mortem completed.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.rules import should_publish_pm_in_general_channel

if TYPE_CHECKING:
    from firefighter.slack.models import Message

if settings.ENABLE_SLACK:
    from firefighter.slack.messages.slack_messages import (
        SlackMessagePostMortemReminder5Days,
        SlackMessagePostMortemReminder5DaysAnnouncement,
    )
    from firefighter.slack.models import Message

logger = logging.getLogger(__name__)

# Days after mitigation to send reminder
POSTMORTEM_REMINDER_DAYS = 5


@shared_task(name="slack.send_postmortem_reminders")
def send_postmortem_reminders() -> None:
    """Send post-mortem completion reminders for incidents mitigated 5+ days ago.

    This task:
    1. Finds incidents that were mitigated at least 5 days ago
    2. Filters for incidents that still need their post-mortem completed
    3. Sends reminders to both the incident channel and #critical-incidents
    4. Tracks sent reminders to avoid duplicates
    """
    # Calculate the cutoff date (5 days ago)
    cutoff_date = timezone.now() - timedelta(days=POSTMORTEM_REMINDER_DAYS)

    # Get incidents that:
    # - Were mitigated at least 5 days ago
    # - Still need post-mortem (P1-P3)
    # - Are in MITIGATED or POST_MORTEM status (not yet closed)
    # - Are not ignored
    incidents_needing_reminder = Incident.objects.filter(
        mitigated_at__lte=cutoff_date,
        mitigated_at__isnull=False,
        _status__in=[
            IncidentStatus.MITIGATED.value,
            IncidentStatus.POST_MORTEM.value,
        ],
        priority__needs_postmortem=True,
        ignore=False,
    ).select_related("conversation", "priority", "environment")

    logger.info(
        f"Found {incidents_needing_reminder.count()} incidents needing post-mortem reminders"
    )

    for incident in incidents_needing_reminder:
        # Check if we already sent a reminder for this incident
        if Message.objects.filter(
            ff_type=SlackMessagePostMortemReminder5Days.id,
            incident=incident,
        ).exists():
            logger.debug(
                f"Skipping incident #{incident.id} - reminder already sent"
            )
            continue

        # Skip if no conversation
        if not hasattr(incident, "conversation") or not incident.conversation:
            logger.warning(
                f"Incident #{incident.id} has no conversation, skipping reminder"
            )
            continue

        # Send reminder to incident channel
        try:
            reminder_message = SlackMessagePostMortemReminder5Days(incident)
            incident.conversation.send_message_and_save(reminder_message)
            logger.info(
                f"Sent post-mortem reminder to incident #{incident.id} channel"
            )
        except Exception:
            logger.exception(
                f"Failed to send post-mortem reminder to incident #{incident.id} channel"
            )
            continue

        # Send announcement to #critical-incidents if applicable
        if should_publish_pm_in_general_channel(incident):
            try:
                tech_incidents_conversation = Conversation.objects.get_or_none(
                    tag="tech_incidents"
                )
                if tech_incidents_conversation:
                    announcement = SlackMessagePostMortemReminder5DaysAnnouncement(
                        incident
                    )
                    tech_incidents_conversation.send_message_and_save(announcement)
                    logger.info(
                        f"Sent post-mortem reminder to tech_incidents for incident #{incident.id}"
                    )
                else:
                    logger.warning(
                        "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
                    )
            except Exception:
                logger.exception(
                    f"Failed to send post-mortem reminder to tech_incidents for incident #{incident.id}"
                )

    logger.info(
        f"Post-mortem reminder task completed. Processed {incidents_needing_reminder.count()} incidents."
    )
