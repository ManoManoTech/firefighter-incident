"""This module contains the logic to open an incident channel and invite responders.

XXX It might be divided into two signals/tasks, one for creating, one for inviting.
XXX Sending the end signal should be done by this signal's caller, not by this signal receiver directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch import receiver
from slack_sdk.errors import SlackApiError

from firefighter.incidents.signals import create_incident_conversation
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentDeclaredAnnouncement,
    SlackMessageIncidentDeclaredAnnouncementGeneral,
)
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.models.user import SlackUser
from firefighter.slack.rules import (
    should_publish_in_general_channel,
    should_publish_in_it_deploy_channel,
)
from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@receiver(signal=create_incident_conversation)
def create_incident_slack_conversation(
    incident: Incident,
    *_args: Any,
    **_kwargs: Any,
) -> int | None:
    """Main process to open an incident channel, set it up and invite responders. It MUST be called when an incident is created.

    Args:
        incident (Incident): The incident to open. It should be saved before calling this function, and have its first incident update created.

    Kwargs:
        jira_extra_fields (dict): Optional dictionary of customer/seller fields for Jira ticket

    """
    # Extract jira_extra_fields from kwargs
    jira_extra_fields = _kwargs.get("jira_extra_fields", {})
    channel: IncidentChannel | None = IncidentChannel.objects.create_incident_channel(
        incident=incident
    )
    if not channel:
        logger.warning("Giving up on Slack channel creation for %s.", incident.id)
        return None

    new_channel_id: str = channel.channel_id
    if not new_channel_id:
        logger.warning("Missing channel id for %s.", incident.id)
        return None
    if not (
        incident.created_by
        and hasattr(incident.created_by, "slack_user")
        and incident.created_by.slack_user
    ):
        if not hasattr(incident.created_by, "slack_user"):
            SlackUser.objects.add_slack_id_to_user(incident.created_by)
        logger.debug(incident.created_by)

    # Join the channel. We are already in the channel if it is a private channel.
    if not incident.private:
        channel.conversations_join()

    channel.set_incident_channel_topic()

    # Add the person that opened the incident in the channel
    if (
        incident.created_by
        and hasattr(incident.created_by, "slack_user")
        and incident.created_by.slack_user
        and incident.created_by.slack_user.slack_id
    ):
        try:
            channel.invite_users([incident.created_by])
        except SlackApiError:
            logger.warning(
                f"Could not import Slack opener user! Slack ID: {incident.created_by.slack_user.slack_id}, User {incident.created_by}, Channel ID {new_channel_id}",
                exc_info=True,
            )
    else:
        logger.warning("Could not find user Slack ID for opener_user!")

    # Send message in the created channel
    channel.send_message_and_save(
        SlackMessageIncidentDeclaredAnnouncement(incident), pin=True
    )

    # Post in general channel #tech-incidents if needed
    if should_publish_in_general_channel(incident, incident_update=None):
        announcement_general = SlackMessageIncidentDeclaredAnnouncementGeneral(incident)

        tech_incidents_conversation = Conversation.objects.get_or_none(
            tag="tech_incidents"
        )
        if tech_incidents_conversation:
            tech_incidents_conversation.send_message_and_save(announcement_general)
        else:
            logger.warning(
                "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
            )

    # Create a response team
    users_list: list[User] = incident.build_invite_list()

    # Invite all users
    incident.conversation.invite_users(users_list)

    # Post in #it-deploy if needed
    if should_publish_in_it_deploy_channel(incident):
        announcement_it_deploy = SlackMessageDeployWarning(incident)
        announcement_it_deploy.id = f"{announcement_it_deploy.id}_{incident.id}"

        it_deploy_conversation = Conversation.objects.get_or_none(tag="it_deploy")
        if it_deploy_conversation:
            it_deploy_conversation.send_message_and_save(announcement_it_deploy)
        else:
            logger.warning(
                "Could not find it_deploy conversation! Is there a channel with tag it_deploy?"
            )

    incident_channel_done.send_robust(
        sender=__name__,
        incident=incident,
        channel=channel,
        jira_extra_fields=jira_extra_fields,
    )
    return None
