from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings

from firefighter.jira_app.client import (
    JiraAPIError,
    JiraUserNotFoundError,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.client import client as jira_client

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User


logger = logging.getLogger(__name__)
RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID


def get_jira_user_from_user(user: User) -> JiraUser:
    """Returns the JiraUser object for a given user, if it exists in DB or can be fetched on Jira API. Returns the default JiraUser if not found."""
    try:
        jira_user = jira_client.get_jira_user_from_user(user)
    except JiraAPIError:
        logger.exception(f"Could not find Jira user for {user.id}")

        logger.warning(f"User {user.id} has no Jira user")
        try:
            jira_user = jira_client.get_jira_user_from_jira_id(
                RAID_DEFAULT_JIRA_QRAFT_USER_ID
            )
        except JiraUserNotFoundError:
            logger.exception(
                f"Could not find Jira user with account id {RAID_DEFAULT_JIRA_QRAFT_USER_ID}"
            )
            jira_user = JiraUser.objects.get(id=RAID_DEFAULT_JIRA_QRAFT_USER_ID)
    return jira_user
