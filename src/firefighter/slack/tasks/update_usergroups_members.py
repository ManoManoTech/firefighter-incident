from __future__ import annotations

import functools
import logging
import operator
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.db import transaction

from firefighter.slack.models import SlackUser, UserGroup
from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@shared_task(
    name="slack.update_usergroups_members_from_slack",
    retry_kwargs={"max_retries": 2},
    default_retry_delay=90,
)
def update_usergroups_members_from_slack_celery(
    *args: Any,
    **options: Any,
) -> dict[str, list[str | None]]:
    """Wrapper around the actual task, as Celery doesn't support passing Django models."""
    fails = update_usergroups_members_from_slack(*args, **options)
    return {"failed_groups": [x.usergroup_id for x in fails]}


@slack_client
def update_usergroups_members_from_slack(
    client: WebClient = DefaultWebClient,
    queryset: QuerySet[UserGroup] | None = None,
) -> list[UserGroup]:
    if queryset is None:
        queryset = UserGroup.objects.all()

    usergroups: QuerySet[UserGroup] = queryset.filter(usergroup_id__isnull=False)

    fails: list[UserGroup] = []
    fails += list(queryset.filter(usergroup_id__isnull=True))
    # Get all usergroups with members
    usergroups_members: dict[str, list[str]] = {}
    usergroups_info: dict[str, dict[str, Any]] = {}
    usergroups_data = UserGroup.objects.fetch_all_usergroups_data(
        client=client, include_users=True
    )

    for usergroup in usergroups:
        if usergroup.usergroup_id is None:
            fails.append(usergroup)
            continue
        usergroup_data = UserGroup.objects.get_usergroup_data_from_list(
            usergroups_data, group_slack_id=usergroup.usergroup_id
        )
        if usergroup_data is None:
            logger.error(f"Could not find usergroup {usergroup.usergroup_id} in Slack")
            continue
        if not isinstance(usergroup.usergroup_id, str):
            err_msg = f"Usergroup {usergroup} has invalid usergroup_id {usergroup.usergroup_id}"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        # Store members
        members_slack_ids = usergroup_data.get("users", [])
        usergroups_members[usergroup.usergroup_id] = members_slack_ids
        logger.debug(
            f"Usergroup {usergroup.usergroup_id} has members {members_slack_ids}"
        )

        # Store info
        usergroup_data_kwargs = UserGroup.objects.parse_slack_response(usergroup_data)

        if usergroup_data_kwargs is None or not isinstance(usergroup_data_kwargs, dict):
            err_msg = f"Usergroup {usergroup} has invalid usergroup_data_kwargs {usergroup_data_kwargs}"  # type: ignore[unreachable]
            raise ValueError(err_msg)

        usergroups_info[usergroup.usergroup_id] = usergroup_data_kwargs

    # Get all usergroups members
    all_members_usergroups: set[str] = set(
        functools.reduce(operator.iadd, usergroups_members.values(), [])
    )

    all_members_mapping: dict[str, User] = {}

    # Get all users from their Slack IDs
    for member_slack_id in all_members_usergroups:
        user = SlackUser.objects.get_user_by_slack_id(member_slack_id)
        if user is not None:
            all_members_mapping[member_slack_id] = user
            logger.debug(f"Found user {user} for Slack ID {member_slack_id}")
            continue

        logger.error(f"Could not retrieve user for Slack ID {member_slack_id}")

    # Usergroups users mapping
    usergroups_members_users: dict[str, list[User]] = {
        k: [all_members_mapping[x] for x in v] for k, v in usergroups_members.items()
    }

    # Save all usergroups members
    with transaction.atomic():
        for usergroup in usergroups:
            if not isinstance(usergroup.usergroup_id, str):
                err_msg = f"Usergroup {usergroup} has invalid usergroup_id {usergroup.usergroup_id}"
                raise TypeError(err_msg)
            if usergroup.usergroup_id in usergroups_members_users:
                usergroup.members.set(usergroups_members_users[usergroup.usergroup_id])
                usergroup.__dict__.update(usergroups_info[usergroup.usergroup_id])
                usergroup.save()
                continue
            fails.append(usergroup)
            logger.warning(
                f"Could not save members and info for non existent usergroup {usergroup.usergroup_id}"
            )
    return fails
