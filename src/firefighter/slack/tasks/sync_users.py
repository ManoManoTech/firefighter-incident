from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task

from firefighter.slack.models import SlackUser
from firefighter.slack.slack_app import DefaultWebClient, SlackApp, slack_client

if TYPE_CHECKING:
    from slack_sdk.web import WebClient

logger = logging.getLogger(__name__)


@shared_task(
    name="slack.sync_users",
    retry_kwargs={"max_retries": 2},
    default_retry_delay=90,
)
def sync_users(*_args: Any, **_options: Any) -> None:
    """Retrieves users from Slack and updates the database (e.g. name, new profile picture, email, active status...)."""
    task()


@slack_client
def get_all_members(
    *args: Any, client: WebClient = DefaultWebClient, **kwargs: Any
) -> list[dict[str, Any]] | None:
    members: list[dict[str, Any]] = []
    slack_users = client.users_list()
    members.extend(slack_users.get("members", []))
    next_cursor: str | None = slack_users.get("response_metadata", {}).get(  # type: ignore[call-overload]
        "next_cursor"
    )
    while next_cursor is not None and next_cursor != "":
        slack_users = client.users_list(cursor=next_cursor)
        ok = slack_users.get("ok")
        if not ok:
            logger.warning("No members found in Slack response")
            return None
        members.extend(slack_users.get("members", []))
        next_cursor = slack_users.get("response_metadata", {}).get("next_cursor")  # type: ignore[call-overload]

    return members


def task(*args: Any, **kwargs: Any) -> None:
    members = get_all_members()
    if members is None:
        logger.error("No members found in Slack response")
        return
    for member in members:
        if member.get("team_id") != SlackApp().details["team_id"]:
            logger.warning("Member %s does not belong to this team", member)
            continue
        if member.get("is_restricted") or member.get("is_ultra_restricted"):
            logger.info("Member %s is restricted, skipping", member)
            continue
        if member.get("deleted"):
            logger.info("Member %s is deleted, skipping", member)
            continue
        if member.get("is_bot") and member.get("id") != SlackApp().details["user_id"]:
            logger.info("Member %s is a bot, skipping", member)
            continue
        SlackUser.objects.update_or_create_from_slack_info(member)
