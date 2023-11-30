from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Never

from django.dispatch.dispatcher import receiver
from django.utils import timezone

from firefighter.firefighter.utils import is_during_office_hours
from firefighter.slack.messages.slack_messages import SlackMessageIncidentDuringOffHours
from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from firefighter.slack.models.incident_channel import IncidentChannel

logger = logging.getLogger(__name__)


@receiver(signal=incident_channel_done)
def incident_channel_done_oncall(channel: IncidentChannel, **kwargs: Never) -> None:
    logger.debug("Signal incident_channel_done received by PagerDuty app.")

    if is_during_office_hours(timezone.localtime()):
        logger.debug("Skipping oncall message for now.")
        return
    channel.send_message_and_save(SlackMessageIncidentDuringOffHours())
