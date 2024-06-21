from __future__ import annotations

import functools
import logging
import operator
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.db import transaction
from slack_sdk.errors import SlackApiError

from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.user import User
logger = logging.getLogger(__name__)


@shared_task(
    name="slack.fetch_conversations_members_from_slack",
    retry_kwargs={"max_retries": 2},
    default_retry_delay=90,
)
def fetch_conversations_members_from_slack_celery(
    *_args: Any,
    queryset: QuerySet[Conversation] | None = None,
    **_options: Any,
) -> dict[str, list[str]]:
    """Wrapper around the actual task, as Celery doesn't support passing Django models."""
    failed_conversations = fetch_conversations_members_from_slack(
        queryset=queryset,
    )
    return {"failed_conversations": [x.channel_id for x in failed_conversations]}


@slack_client
def fetch_conversations_members_from_slack(
    client: WebClient = DefaultWebClient,
    queryset: QuerySet[Conversation] | None = None,
) -> list[Conversation]:
    """Update the members and metadata of Slack Conversations in DB, from Slack API.

    Only fetches conversations that are not IncidentChannels.

    Args:
        client (WebClient, optional): Slack SDK client. Defaults to DefaultWebClient.
        queryset (Optional[QuerySet[Conversation]], optional): Conversation to update. Defaults to None. If None, all applicable

    Returns:
        list[Conversation]: List of conversations that could not be updated.

    Raises:
        TypeError: If the members list is not a list.
    """
    conversations: QuerySet[Conversation] = (
        queryset
        if queryset and queryset.model != Conversation
        else Conversation.objects.not_incident_channel(queryset)
    )

    fails: list[Conversation] = []
    fails += list(conversations.filter(channel_id__isnull=True))

    conversations_members: dict[str, list[str]] = {}
    conversations_info: dict[str, dict[str, Any]] = {}

    for conversation in conversations:
        # Fetch members IDs
        try:
            conversation_members: list[str] = client.conversations_members(
                channel=conversation.channel_id
            ).get("members", [])
        except SlackApiError:
            logger.warning(f"Could not fetch members for {conversation.channel_id}")
            continue
        if not isinstance(conversation_members, list):
            err_msg = f"conversation_members is not a list: {conversation_members}"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        # Fetch conversation info
        conversation_info = client.conversations_info(channel=conversation.channel_id)

        # Save members
        members_slack_ids = conversation_members
        conversations_members[conversation.channel_id] = members_slack_ids

        # Save info (channel_id, channel_name, channel_type, status)
        conversation_data_kwargs_tup = Conversation.objects.parse_slack_response(
            conversation_info
        )
        conversation_data_kwargs = {
            "name": conversation_data_kwargs_tup[1],
            "_type": conversation_data_kwargs_tup[2],
            "_status": conversation_data_kwargs_tup[3],
        }

        conversations_info[conversation.channel_id] = conversation_data_kwargs

    # Get all usergroups members
    all_members_usergroups: set[str] = set(
        functools.reduce(operator.iadd, conversations_members.values(), [])
    )

    all_members_mapping: dict[str, User] = {}

    # Get all users from their Slack IDs
    for member_slack_id in all_members_usergroups:
        user = SlackUser.objects.get_user_by_slack_id(member_slack_id)
        if user is not None:
            all_members_mapping[member_slack_id] = user
            logger.info(user)
            continue

        logger.error(f"Could not retrieve user for Slack ID {member_slack_id}")

    # Usergroups users mapping
    usergroups_members_users: dict[str, list[User]] = {
        k: [all_members_mapping[y] for y in v] for k, v in conversations_members.items()
    }
    logger.debug(usergroups_members_users)

    # Save all usergroups members
    with transaction.atomic():
        for conversation in conversations:
            if not isinstance(conversation.channel_id, str):
                err_msg = f"Conversation {conversation.channel_id} has no channel_id"  # type: ignore[unreachable]
                raise TypeError(err_msg)
            if conversation.channel_id in usergroups_members_users:
                conversation.members.set(
                    usergroups_members_users[conversation.channel_id]
                )
                conversation.__dict__.update(
                    conversations_info[conversation.channel_id]
                )
                conversation.save()
                continue
            fails.append(conversation)
            logger.warning(
                f"Could not save members and info for non existent conversation {conversation.channel_id}"
            )
    return fails
