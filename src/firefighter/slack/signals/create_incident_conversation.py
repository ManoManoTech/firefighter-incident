"""This module contains the logic to open an incident channel and invite responders.

XXX It might be divided into two signals/tasks, one for creating, one for inviting.
XXX Sending the end signal should be done by this signal's caller, not by this signal receiver directly.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from django.dispatch import receiver
from slack_sdk.errors import SlackApiError

from firefighter.incidents.signals import create_incident_conversation
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentDeclaredAnnouncement,
    SlackMessageIncidentDeclaredAnnouncementGeneral,
)
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.models.user import SlackUser
from firefighter.slack.rules import (
    should_publish_in_general_channel,
    should_publish_in_it_deploy_channel,
)
from firefighter.slack.signals import incident_channel_done
from firefighter.slack.slack_app import DefaultWebClient
from firefighter.slack.utils.test_channels import get_or_create_test_conversation

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@receiver(signal=create_incident_conversation)
def create_incident_slack_conversation(  # noqa: PLR0912, PLR0915
    incident: Incident,
    *_args: Any,
    **_kwargs: Any,
) -> int | None:
    """Main process to open an incident channel, set it up and invite responders. It MUST be called when an incident is created.

    Args:
        incident (Incident): The incident to open. It should be saved before calling this function, and have its first incident update created.

    """
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
    invited_creator = False
    creator_slack_id = None
    if (
        incident.created_by
        and hasattr(incident.created_by, "slack_user")
        and incident.created_by.slack_user
        and incident.created_by.slack_user.slack_id
    ):
        creator_slack_id = incident.created_by.slack_user.slack_id
        try:
            # Check if the invitation was successful by checking if the user is now a member
            members_before = set(channel.incident.members.all())
            channel.invite_users([incident.created_by])
            members_after = set(channel.incident.members.all())

            # If the user was added to members, invitation succeeded
            if incident.created_by in members_after and incident.created_by not in members_before:
                invited_creator = True
                logger.info(f"Successfully invited creator {creator_slack_id}")
            else:
                logger.warning(f"Creator {creator_slack_id} was not added to incident members - invitation may have failed")

        except SlackApiError:
            logger.warning(
                f"Could not import Slack opener user! Slack ID: {creator_slack_id}, User {incident.created_by}, Channel ID {new_channel_id}",
                exc_info=True,
            )
    else:
        logger.warning("Could not find user Slack ID for opener_user!")

    # In test mode, if creator invitation failed, try to get the Slack user ID from kwargs
    test_mode = os.getenv("TEST_MODE", "False").lower() == "true"
    slack_user_id = _kwargs.get("slack_user_id")

    logger.info(f"Test mode: {test_mode}, invited_creator: {invited_creator}")
    logger.info(f"Creator stored slack_id: {creator_slack_id}, event slack_user_id: {slack_user_id}")
    if test_mode and not invited_creator and slack_user_id:
        logger.info(f"Test mode: Attempting to invite creator using event Slack ID {slack_user_id}")
        try:
            # Invite directly using the Slack user ID from the event
            from firefighter.slack.slack_app import slack_client

            @slack_client
            def invite_test_user(channel_instance, user_id, client=DefaultWebClient):
                return channel_instance._invite_users_to_conversation({user_id}, client)

            invite_test_user(channel, slack_user_id)
            logger.info(f"Test mode: Successfully invited creator via Slack ID {slack_user_id}")
        except SlackApiError:
            logger.warning(
                f"Test mode: Could not invite creator via Slack ID {slack_user_id}",
                exc_info=True,
            )

    # Send message in the created channel
    channel.send_message_and_save(
        SlackMessageIncidentDeclaredAnnouncement(incident, slack_user_id=slack_user_id), pin=True
    )

    # Post in general channel #tech-incidents if needed
    if should_publish_in_general_channel(incident, incident_update=None):
        announcement_general = SlackMessageIncidentDeclaredAnnouncementGeneral(incident, slack_user_id=slack_user_id)

        tech_incidents_conversation = get_or_create_test_conversation("tech_incidents")
        if tech_incidents_conversation:
            tech_incidents_conversation.send_message_and_save(announcement_general)
        else:
            logger.warning(
                "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
            )

    # Create a response team
    users_list: list[User] = incident.build_invite_list()

    # Invite all users
    incident.conversation.invite_users(users_list, slack_user_id=slack_user_id)

    # Post in #it-deploy if needed
    if should_publish_in_it_deploy_channel(incident):
        announcement_it_deploy = SlackMessageDeployWarning(incident)
        announcement_it_deploy.id = f"{announcement_it_deploy.id}_{incident.id}"

        it_deploy_conversation = get_or_create_test_conversation("it_deploy")
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
    )
    return None
