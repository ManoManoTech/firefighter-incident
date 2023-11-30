from __future__ import annotations

import logging

from celery import shared_task

from firefighter.incidents.models.user import User
from firefighter.jira_app.client import JiraUserNotFoundError, client
from firefighter.jira_app.models import JiraUser

logger = logging.getLogger(__name__)


def add_jira_slack_relationship(user: User) -> JiraUser | None:
    try:
        jira_api_user = client.get_jira_user_from_user(user)
    except JiraUserNotFoundError:
        logger.warning(f"User not found with Jira API '{user.id}'")
        return None
    jira_user_id = jira_api_user.id

    if jira_api_user is None or jira_user_id == "":
        logger.warning(f"Invalid Jira user ID '{jira_user_id}' for User {user.id}")
        return None
    # XXX Check None and valid

    jira_user, _ = JiraUser.objects.update_or_create(
        user=user, defaults={"id": jira_user_id}
    )
    logger.info(f"Added user {jira_user}")
    return jira_user


@shared_task(name="raid.jira_slack_full")
def add_jira_slack_to_all_full() -> None:
    for user in User.objects.exclude(is_active=False).exclude(username=""):
        add_jira_slack_relationship(user)


@shared_task(name="raid.jira_slack_only_missing")
def add_jira_slack_to_all_only_missing() -> None:
    for user in (
        User.objects.exclude(is_active=False)
        .exclude(username="")
        .filter(jira_user__isnull=True)
    ):
        add_jira_slack_relationship(user)
