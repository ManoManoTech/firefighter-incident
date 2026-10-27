"""Tell Slack about the origin of an incident, and about partners added by users."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.dispatch.dispatcher import receiver
from django.urls import reverse
from slack_sdk.errors import SlackApiError

from firefighter.incidents.origin import origin_label
from firefighter.incidents.signals import incident_origin_updated, partner_created
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentOriginUpdated,
    SlackMessagePartnerCreated,
)
from firefighter.slack.models.conversation import (
    Conversation,
    incident_has_writable_channel,
)

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.partner import Partner
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@receiver(signal=incident_origin_updated)
def incident_origin_updated_handler(
    sender: Any, incident: Incident, user: User | None = None, **kwargs: Any
) -> None:
    """Show the new origin to everyone in the incident channel."""
    # Nothing can be posted in an archived channel: Slack answers `is_archived`
    if not incident_has_writable_channel(incident):
        return
    conversation = incident.conversation
    slack_user = getattr(user, "slack_user", None) if user else None
    try:
        conversation.send_message_and_save(
            SlackMessageIncidentOriginUpdated(
                incident,
                origin_label(incident),
                slack_user.slack_id if slack_user else None,
            )
        )
    except SlackApiError:
        logger.exception("Could not post the origin of incident #%s", incident.id)


@receiver(signal=partner_created)
def partner_created_handler(
    sender: Any, partner: Partner, incident: Incident, **kwargs: Any
) -> None:
    """Ask the IMPACT team to review a partner a user just added."""
    support_conversation = Conversation.objects.get_or_none(tag="dev_firefighter")
    if support_conversation is None:
        logger.warning(
            "Could not find the dev_firefighter conversation to report the new partner %r",
            partner.name,
        )
        return
    admin_url = settings.BASE_URL + reverse(
        "admin:incidents_partner_change", args=[partner.id]
    )
    try:
        support_conversation.send_message_and_save(
            SlackMessagePartnerCreated(partner.name, incident, admin_url)
        )
    except SlackApiError:
        logger.exception("Could not report the new partner %r", partner.name)
