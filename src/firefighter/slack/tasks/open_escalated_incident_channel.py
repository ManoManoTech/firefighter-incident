"""Open the Slack channel of an incident escalated from P4/P5 to P1-P3.

P4/P5 incidents have no Slack channel, only a Jira ticket. When one is escalated to a critical
priority (from IMPACT or through the Jira priority sync), it needs the same channel as an
incident declared critical: this task opens it, through the same signal as a declaration, so
responders are invited from the incident category and the channel is fully set up.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.user import User
from firefighter.incidents.signals import create_incident_conversation
from firefighter.slack.messages.slack_messages import SlackMessageIncidentEscalatedDM

logger = logging.getLogger(__name__)

ESCALATION_LOCK_TIMEOUT = 10 * 60
"""Seconds during which a second escalation of the same incident opens no other channel."""


def needs_escalation_channel(incident: Incident) -> bool:
    """A critical incident, still being handled, with no Slack channel yet."""
    return (
        incident.priority.value <= 3
        and IncidentStatus.OPEN <= incident.status <= IncidentStatus.MITIGATED
        and not hasattr(incident, "conversation")
    )


@shared_task(name="slack.open_escalated_incident_channel")
def open_escalated_incident_channel(
    incident_id: int, escalated_by_id: str | None = None
) -> None:
    """Open the incident channel, then tell the Jira ticket and the people involved.

    Args:
        incident_id: the escalated incident.
        escalated_by_id: the user who escalated it, None when it came from the Jira sync.
    """
    # Two escalations close together (e.g. duplicated Jira webhooks) must open one channel.
    if not cache.add(
        f"escalation_channel:{incident_id}", value=True, timeout=ESCALATION_LOCK_TIMEOUT
    ):
        logger.info("Channel of escalated incident #%s already being opened", incident_id)
        return

    incident = Incident.objects.select_related("priority").get(pk=incident_id)
    if not needs_escalation_channel(incident):
        logger.info("Escalated incident #%s needs no new channel", incident_id)
        return

    create_incident_conversation.send(
        "open_escalated_incident_channel", incident=incident, announce_globally=False
    )
    incident = Incident.objects.select_related("priority", "created_by").get(pk=incident_id)
    if not hasattr(incident, "conversation"):
        logger.warning("Could not open the channel of escalated incident #%s", incident_id)
        return

    escalated_by = (
        User.objects.filter(pk=escalated_by_id).first() if escalated_by_id else None
    )
    if escalated_by is not None:
        # The category's responders are invited, the escalator is not necessarily one of them.
        incident.conversation.invite_users([escalated_by])

    _comment_jira_ticket(incident)
    _notify_people_involved(incident, escalated_by)


def _comment_jira_ticket(incident: Incident) -> None:
    if not settings.ENABLE_RAID or getattr(incident, "jira_ticket", None) is None:
        return
    from firefighter.raid.client import client

    try:
        client.add_comment(
            incident.jira_ticket.id,
            f"This incident was escalated to {incident.priority.name} in IMPACT. Its Slack "
            f"channel is now open: [#{incident.conversation.name}|{incident.conversation.link}]",
        )
    except Exception:
        logger.exception(
            "Failed to comment the escalation on Jira ticket %s for incident #%s",
            incident.jira_ticket.id,
            incident.id,
        )


def _notify_people_involved(incident: Incident, escalated_by: User | None) -> None:
    recipients = {
        user for user in (incident.created_by, escalated_by) if user is not None
    }
    for user in recipients:
        slack_user = getattr(user, "slack_user", None)
        if slack_user is None:
            continue
        try:
            slack_user.send_private_message(SlackMessageIncidentEscalatedDM(incident))
        except SlackApiError:
            logger.exception(
                "Could not DM %s about the escalation of incident #%s", user.id, incident.id
            )
