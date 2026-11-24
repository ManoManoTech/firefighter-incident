"""Tests for the daily Slack usergroups members sync.

A usergroup that Slack no longer returns (deleted, or disabled: `usergroups.list`
omits disabled groups) must keep raising an ERROR, and that ERROR must name the
group and the incident categories that still depend on it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.factories import IncidentCategoryFactory
from firefighter.slack.factories import SlackUserFactory
from firefighter.slack.models.user_group import UserGroup
from firefighter.slack.tasks.update_usergroups_members import (
    update_usergroups_members_from_slack,
    update_usergroups_members_from_slack_celery,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet

LOGGER_NAME = "firefighter.slack.tasks.update_usergroups_members"


def _slack_client(usergroups: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    client.usergroups_list.return_value = {"ok": True, "usergroups": usergroups}
    return client


def _only(group: UserGroup) -> QuerySet[UserGroup]:
    # Data migrations seed real usergroups: scope each run to the group under test.
    return UserGroup.objects.filter(pk=group.pk)


def _error_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER_NAME and record.levelno == logging.ERROR
    ]


@pytest.mark.django_db
class TestMissingUsergroup:
    def test_error_names_the_group_and_its_incident_categories(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        group = UserGroup.objects.create(
            name="impact-catalog-product-structure",
            handle="impact-catalog-product-structure",
            usergroup_id="S_DISABLED",
        )
        group.incident_categories.add(
            IncidentCategoryFactory.create(name="Product Structure"),
            IncidentCategoryFactory.create(name="Catalog Access"),
        )

        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            fails = update_usergroups_members_from_slack(
                client=_slack_client([]), queryset=_only(group)
            )

        assert _error_messages(caplog) == [
            (
                "Slack usergroup @impact-catalog-product-structure (S_DISABLED) not found "
                "in Slack (deleted or disabled). Linked incident categories: Catalog Access, "
                "Product Structure. Its members are no longer synced."
            )
        ]
        assert fails == [group]

    def test_error_says_when_the_group_has_no_incident_category(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        group = UserGroup.objects.create(
            name="orphan", handle="orphan", usergroup_id="S_ORPHAN"
        )

        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            update_usergroups_members_from_slack(
                client=_slack_client([]), queryset=_only(group)
            )

        assert _error_messages(caplog) == [
            (
                "Slack usergroup @orphan (S_ORPHAN) not found in Slack (deleted or "
                "disabled). Not linked to any incident category. Its members are no "
                "longer synced."
            )
        ]


@pytest.mark.django_db
def test_existing_usergroup_is_synced_without_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    member = SlackUserFactory.create(slack_id="U_MEMBER")
    group = UserGroup.objects.create(
        name="old name", handle="catalog", usergroup_id="S_CATALOG"
    )
    slack_group = {
        "id": "S_CATALOG",
        "name": "new name",
        "handle": "catalog",
        "description": "Catalog team",
        "is_external": False,
        "users": ["U_MEMBER"],
    }

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        fails = update_usergroups_members_from_slack(
            client=_slack_client([slack_group]), queryset=_only(group)
        )

    assert _error_messages(caplog) == []
    assert fails == []
    group.refresh_from_db()
    assert group.name == "new name"
    assert list(group.members.all()) == [member.user]


@pytest.mark.django_db
def test_celery_task_reports_missing_usergroups_as_failed() -> None:
    UserGroup.objects.create(name="gone", handle="gone", usergroup_id="S_GONE")

    result = update_usergroups_members_from_slack_celery(client=_slack_client([]))

    assert "S_GONE" in result["failed_groups"]
