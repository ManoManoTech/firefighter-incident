from __future__ import annotations

import logging
import os
import textwrap
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.conversation import Conversation, ConversationManager
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import DefaultWebClient, slack_client
from firefighter.slack.utils import channel_name_from_incident

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient
    from slack_sdk.web.slack_response import SlackResponse

    from firefighter.incidents.models import User

APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME
SLACK_APP_EMOJI: str = settings.SLACK_APP_EMOJI
logger = logging.getLogger(__name__)


class IncidentChannelManager(ConversationManager["IncidentChannel"]):
    @slack_client
    def create_incident_channel(
        self,
        incident: Incident,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> IncidentChannel | None:
        channel_name = channel_name_from_incident(incident)

        logger.debug("Creating channel #%s", channel_name)
        channel: IncidentChannel | None = super().create_channel(
            name=channel_name,
            client=client,
            incident=incident,
            is_private=incident.private,
            **kwargs,
        )
        return channel


class IncidentChannel(Conversation):
    objects: IncidentChannelManager = IncidentChannelManager()  # type: ignore[assignment]

    incident = models.OneToOneField[Incident, Incident](
        Incident,
        on_delete=models.CASCADE,
        related_name="conversation",
    )
    if TYPE_CHECKING:
        incident_id: int

    @slack_client
    def rename_if_needed(self, client: WebClient = DefaultWebClient) -> bool | None:
        new_name = self.channel_name_from_incident()

        if self.name != new_name:
            try:
                slack_conv = client.conversations_rename(
                    channel=self.channel_id, name=new_name
                )
            except SlackApiError:
                logger.exception(f"Could not rename channel {self.id}.")
                return None

            (
                channel_id,
                channel_name,
                channel_type,
                status,
            ) = Conversation.objects.parse_slack_response(slack_conv=slack_conv)

            self.name = channel_name
            self.status = status
            self.channel_id = channel_id
            self.type = channel_type
            self.save()
            return True
        return None

    def channel_name_from_incident(self, incident: Incident | None = None) -> str:
        if incident and self.incident != incident:
            raise ValueError(
                "The incident passed as argument does not match the incident of the channel."
            )
        if incident is None:
            incident = self.incident

        return channel_name_from_incident(incident)

    @slack_client
    def set_incident_channel_topic(
        self, client: WebClient = DefaultWebClient
    ) -> SlackResponse | None:
        incident: Incident = self.incident
        topic = f"Incident - {incident.priority.emoji} {incident.priority.name}  - {incident.status.label} - {incident.component.group.name} - {incident.component.name} - {SLACK_APP_EMOJI} <{incident.status_page_url + '?utm_medium=FireFighter+Slack&utm_source=Slack+Topic&utm_campaign=Slack+Topic+Link'}| {APP_DISPLAY_NAME} Status>"

        if len(topic) > 250:
            logger.warning(
                f"Generated a Slack topic longer than the maximum! It will be truncated to 250 chars. Topic: {topic}"
            )
            topic = textwrap.shorten(topic, width=250, placeholder="...")

        return self.update_topic(topic, client=client)

    @slack_client
    def invite_users(
        self, users_mapped: list[User], client: WebClient = DefaultWebClient, slack_user_id: str | None = None
    ) -> None:
        """Invite users to the conversation, if they have a Slack user linked and are active.

        Try to invite all users as batch, but if some fail, continue individually.
        """
        users_with_slack: list[User] = self._get_active_slack_users(users_mapped)
        users_with_slack = list(set(users_with_slack))  # Remove duplicates

        user_id_list: set[str] = self._get_slack_id_list(users_with_slack, slack_user_id)
        if not user_id_list:
            logger.info(f"No users to invite to the conversation {self}.")
            return

        logger.info(f"Inviting users with SlackIDs: {user_id_list}")

        invited_slack_user_ids = self._invite_users_to_conversation(
            user_id_list, client
        )
        invited_users = {
            u
            for u in users_with_slack
            if u.slack_user and u.slack_user.slack_id in invited_slack_user_ids
        }

        if invited_slack_user_ids != set(user_id_list):
            logger.warning(
                f"Could not invite all users to the conversation {self}. Missing users: {user_id_list - invited_slack_user_ids}"
            )

        self.incident.members.add(*invited_users)

    @staticmethod
    def _get_active_slack_users(users_mapped: list[User]) -> list[User]:
        """Filter out users that have no Slack user linked or are disabled."""
        users_with_slack: list[User] = []

        for user in users_mapped:
            user_with_slack = SlackUser.objects.add_slack_id_to_user(user)
            if user_with_slack is not None and user_with_slack.is_active:
                users_with_slack.append(user_with_slack)
            else:
                logger.warning(
                    f"User {user.id} has no Slack user linked or is disabled."
                )

        return users_with_slack

    @staticmethod
    def _get_slack_id_list(users_with_slack: list[User], slack_user_id: str | None = None) -> set[str]:
        from firefighter.firefighter.settings.settings_utils import config  # noqa: PLC0415
        
        test_mode = config("TEST_MODE", default="False", cast=str).lower() == "true"
        slack_ids = set()
        
        for user in users_with_slack:
            if not user:
                continue
            
            # In test mode, handle user ID mapping more carefully
            if test_mode and hasattr(user, 'slack_user') and user.slack_user and user.slack_user.slack_id:
                stored_slack_id = user.slack_user.slack_id
                
                # Skip users with old production IDs that don't exist in test workspace
                # Old production IDs are alphabetic only, while test IDs contain numbers
                if stored_slack_id.startswith('U') and not any(c.isdigit() for c in stored_slack_id):
                    logger.info(f"Test mode: Skipping user {user.id} with production slack_id {stored_slack_id}")
                    continue
                else:
                    # Valid test ID, use it
                    slack_ids.add(stored_slack_id)
            elif hasattr(user, 'slack_user') and user.slack_user and user.slack_user.slack_id:
                # Non-test mode: use stored slack_id
                slack_ids.add(user.slack_user.slack_id)
        
        # In test mode, ensure the current user (from the event) is included if provided
        if test_mode and slack_user_id and slack_user_id not in slack_ids:
            logger.info(f"Test mode: Adding current user's Slack ID {slack_user_id} to invitation list")
            slack_ids.add(slack_user_id)
        
        return slack_ids

    def _invite_users_to_conversation(
        self, user_id_list: set[str], client: WebClient
    ) -> set[str]:
        # In test mode, filter out invalid user IDs to prevent errors
        from firefighter.firefighter.settings.settings_utils import config  # noqa: PLC0415
        test_mode = config("TEST_MODE", default="False", cast=str).lower() == "true"

        if test_mode:
            logger.info(f"Test mode: Attempting to invite users with IDs: {user_id_list}")

        try:
            done = self._invite_users_with_slack_id(user_id_list, client)
        except SlackApiError as e:
            logger.warning(
                f"Could not batch import Slack users! Slack IDs: {user_id_list}",
                exc_info=True,
            )

            # In test mode, if batch invite fails due to user_not_found, skip individual retries
            if test_mode and e.response.get("error") == "user_not_found":
                logger.info("Test mode: Skipping individual invitations for user_not_found errors")
                return set()

            # If batch invite fails due to already_in_channel, consider all users as successfully invited
            if e.response.get("error") == "already_in_channel":
                logger.debug("All users already in channel - this is expected")
                return user_id_list

            done = self._invite_users_to_conversation_individually(user_id_list, client)
        return done

    def _invite_users_with_slack_id(
        self, user_id_list: set[str], client: WebClient
    ) -> set[str]:
        client.conversations_invite(
            channel=self.channel_id,
            users=list(user_id_list),
        )

        logger.info(
            f"Imported Slack IDs: {user_id_list} in channel {self.channel_id} for incident {self.incident.id}"
        )
        return user_id_list

    def _invite_users_to_conversation_individually(
        self, slack_user_ids: set[str], client: WebClient
    ) -> set[str]:
        from firefighter.firefighter.settings.settings_utils import config  # noqa: PLC0415
        test_mode = config("TEST_MODE", default="False", cast=str).lower() == "true"

        done = set()
        for slack_user_id in slack_user_ids:
            try:
                self._invite_users_with_slack_id({slack_user_id}, client)
                done.add(slack_user_id)
            except SlackApiError as e:
                error_type = e.response.get("error", "unknown_error")

                if test_mode and error_type == "user_not_found":
                    logger.info(f"Test mode: Skipping user_not_found error for user ID {slack_user_id}")
                    continue

                if error_type == "already_in_channel":
                    logger.debug(f"User {slack_user_id} is already in channel - this is expected")
                    done.add(slack_user_id)  # Consider as successfully "invited"
                    continue

                logger.warning(
                    f"Could not import Slack user! User ID: {slack_user_id} - {error_type}",
                    exc_info=True,
                )
        return done


class BatchInviteError(SlackApiError):
    pass
