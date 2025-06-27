from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from django.db.models import Q
from django.dispatch.dispatcher import receiver

from firefighter.incidents import signals
from firefighter.incidents.models.user import User
from firefighter.slack.models.user_group import UserGroup
from firefighter.slack.slack_app import SlackApp

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models.query import QuerySet

    from firefighter.incidents.models.incident import Incident
    from firefighter.slack.models.conversation import Conversation

logger = logging.getLogger(__name__)


@receiver(signal=signals.get_invites)
def get_invites_from_slack(incident: Incident, **_kwargs: Any) -> Iterable[User]:
    """New version using cached users instead of querying Slack API."""
    # In test mode, skip usergroup invitations if disabled
    test_mode = os.getenv("TEST_MODE", "False").lower() == "true"
    usergroups_enabled = os.getenv("ENABLE_SLACK_USERGROUPS", "True").lower() == "true"

    if test_mode and not usergroups_enabled:
        logger.info("Test mode: Skipping Slack usergroup invitations")
        return []

    # Prepare sub-queries
    slack_usergroups: QuerySet[UserGroup] = incident.component.usergroups.all()
    slack_conversations: QuerySet[Conversation] = incident.component.conversations.all()

    # We make sure to exclude the bot user, and avoid duplicates with distinct()
    # Also make sure that all users have related SlackUser and a slack_id
    queryset = (
        User.objects.filter(slack_user__isnull=False)
        .exclude(slack_user__slack_id=SlackApp().details["user_id"])
        .exclude(slack_user__slack_id="")
        .exclude(slack_user__slack_id__isnull=True)
        .filter(
            Q(conversation__in=slack_conversations) | Q(usergroup__in=slack_usergroups)
        )
        .distinct()
    )
    return set(queryset)


@receiver(signal=signals.get_invites)
def get_invites_from_slack_for_p1(incident: Incident, **kwargs: Any) -> Iterable[User]:
    # In test mode, skip usergroup invitations if disabled
    test_mode = os.getenv("TEST_MODE", "False").lower() == "true"
    usergroups_enabled = os.getenv("ENABLE_SLACK_USERGROUPS", "True").lower() == "true"

    if test_mode and not usergroups_enabled:
        logger.info("Test mode: Skipping P1 Slack usergroup invitations")
        return []

    if incident.priority.value > 1:
        return []

    if incident.private:
        return []

    slack_usergroups: QuerySet[UserGroup] = UserGroup.objects.filter(
        tag="invited_for_all_public_p1"
    )

    queryset = (
        User.objects.filter(slack_user__isnull=False)
        .exclude(slack_user__slack_id=SlackApp().details["user_id"])
        .exclude(slack_user__slack_id="")
        .exclude(slack_user__slack_id__isnull=True)
        .filter(usergroup__in=slack_usergroups)
        .distinct()
    )
    return set(queryset)
