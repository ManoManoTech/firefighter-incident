from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.firefighter.utils import get_first_in, get_in
from firefighter.incidents.models import IncidentCategory, User
from firefighter.slack.slack_app import DefaultWebClient, SlackApp, slack_client

if TYPE_CHECKING:
    from collections.abc import Sequence  # noqa: F401

    from django_stubs_ext.db.models.manager import RelatedManager  # noqa: F401
    from slack_sdk.web.client import WebClient
logger = logging.getLogger(__name__)


class UserGroupManager(models.Manager["UserGroup"]):
    @staticmethod
    @slack_client
    def fetch_usergroup(
        group_slack_id: str | None = None,
        group_handle: str | None = None,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> UserGroup | None:
        """Import a "usergroup" from Slack and return its UserGroup model.
        Either group_slack_id or group_handle must be provided.

        Args:
            group_slack_id (str | None, optional): The Slack usergroup id of the usergroup to import. Usually starts with `S`. Defaults to None.
            group_handle (str | None, optional): Handle (@xxx) of the usergroup to import. Defaults to None.
            client (WebClient, optional): Slack client. Defaults to DefaultWebClient.
            **kwargs: Additional keyword arguments to pass to created UserGroup model.

        Returns:
            UserGroup | None: UserGroup model or None if not found
        """
        slack_response_usergroups = UserGroupManager.fetch_all_usergroups_data(
            client=client
        )

        usergroup = UserGroupManager.get_usergroup_data_from_list(
            usergroups=slack_response_usergroups,
            group_slack_id=group_slack_id,
            group_handle=group_handle,
        )
        if not usergroup:
            logger.warning(
                f"Could not find matching group! group_slack_id: {group_slack_id}; group_handle: {group_handle}"
            )
            return None
        logger.debug(usergroup)

        return UserGroup(
            **UserGroupManager.parse_slack_response(usergroup),
            **kwargs,
        )

    @staticmethod
    def parse_slack_response(slack_usergroup: dict[str, Any]) -> dict[str, Any]:
        name = get_in(slack_usergroup, "name")
        handle = get_in(slack_usergroup, "handle")
        usergroup_id = get_in(slack_usergroup, "id")
        description = get_in(slack_usergroup, "description")
        is_external = get_in(slack_usergroup, "is_external")

        return {
            "name": name,
            "handle": handle,
            "usergroup_id": usergroup_id,
            "description": description,
            "is_external": is_external,
        }

    @staticmethod
    def fetch_all_usergroups_data(
        client: WebClient = DefaultWebClient,
        *,
        include_users: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch all usergroups from firefighter.slack.

        Returns the list of usergroups
        """
        slack_response_usergroups = client.usergroups_list(include_users=include_users)

        ug_list = get_in(slack_response_usergroups, "usergroups")
        if not isinstance(ug_list, list):
            err_msg = (
                f"Expected usergroups to be a list, but got {type(ug_list)}: {ug_list}"
            )

            raise TypeError(err_msg)
        return ug_list

    @staticmethod
    def get_usergroup_data_from_list(
        usergroups: list[dict[str, Any]],
        group_slack_id: str | None = None,
        group_handle: str | None = None,
    ) -> dict[str, Any] | None:
        if group_slack_id is None and group_handle is None:
            raise ValueError("Either group_slack_id or group_handle must be provided.")

        if group_slack_id:
            usergroup = get_first_in(get_in(usergroups, []), "id", (group_slack_id,))
        elif group_handle:
            usergroup = get_first_in(
                get_in(usergroups, []),
                "handle",
                (group_handle,),
            )
        else:
            return None

        return usergroup

    @staticmethod
    def fetch_usergroup_data(
        group_slack_id: str | None = None, group_handle: str | None = None
    ) -> dict[str, Any] | None:
        usergroups_data = UserGroupManager.fetch_all_usergroups_data()
        return UserGroupManager.get_usergroup_data_from_list(
            usergroups_data, group_slack_id, group_handle
        )


class UserGroup(models.Model):
    """Model a Slack API UserGroup.
    Reference: https://api.slack.com/types/usergroup.
    """

    objects: UserGroupManager = UserGroupManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Friendly name of the group. Corresponds to the `name` field in the Slack API. Max 80 characters.",
    )
    handle = models.CharField(
        max_length=80,
        blank=True,
        help_text="Indicates the value used to notify group members via a mention. The handle does not include the leading @. Corresponds to the `handle` field in the Slack API. Max 80 characters.",
    )
    description = models.CharField(
        max_length=140,
        blank=True,
        help_text="A short description of the group. Corresponds to the `description` field in the Slack API. Max 140 characters.",
    )
    usergroup_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        unique=True,
        help_text="The Slack usergroup ID of the usergroup. Usually starts with `S`.",
    )

    is_external = models.BooleanField(
        default=False,
        help_text="Is this an external group, from an external Slack Workspace? Corresponds to the `is_external` field in the Slack API.",
    )

    incident_categories = models.ManyToManyField["IncidentCategory", "IncidentCategory"](
        IncidentCategory,
        related_name="usergroups",
        blank=True,
        help_text="Incident created with this usergroup automatically add the group members to these issue categories.",
    )

    tag = models.CharField(
        max_length=80,
        blank=True,
        help_text="Used by FireFighter internally to mark special user groups (e.g. @team-secu, @team-incidents...). Must be empty or unique.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    members = models.ManyToManyField(User, blank=True)

    class Meta(TypedModelMeta):
        verbose_name = "Slack user group"
        verbose_name_plural = "Slack user groups"

    def __str__(self) -> str:
        return f"@{self.handle} ({self.usergroup_id})"

    @property
    def link(self) -> str:
        """Regular HTTPS link to the conversation through Slack.com."""
        return f"https://app.slack.com/client/{SlackApp().details['team_id']}/browse-user-groups/user_groups/{self.usergroup_id}"
