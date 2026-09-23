"""Tests for the Slack providers of the `get_invites` signal.

A private incident must only invite the members of the usergroups linked to its
incident category: the usergroup tagged `invited_for_all_public_p1` is reserved
to public P1 incidents.
"""

from __future__ import annotations

import pytest

from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.models.user import User
from firefighter.slack.factories import SlackUserFactory
from firefighter.slack.models.user_group import UserGroup
from firefighter.slack.signals.get_users import (
    get_invites_from_slack,
    get_invites_from_slack_for_p1,
)


def _slack_user() -> User:
    user = UserFactory.create()
    SlackUserFactory.create(user=user)
    return user


@pytest.fixture
def p1_group_member() -> User:
    member = _slack_user()
    group = UserGroup.objects.create(
        name="Firefighters P1",
        handle="firefighters-p1",
        usergroup_id="S_FIREFIGHTERS_P1",
        tag="invited_for_all_public_p1",
    )
    group.members.add(member)
    return member


@pytest.fixture
def category_group_member() -> User:
    return _slack_user()


def _make_incident(
    category_group_member: User, *, priority_value: int, private: bool
) -> Incident:
    category = IncidentCategoryFactory.create(private=private)
    group = UserGroup.objects.create(
        name="Security data leak",
        handle="security-data-leak",
        usergroup_id="S_SECURITY_DATA_LEAK",
    )
    group.incident_categories.add(category)
    group.members.add(category_group_member)
    priority = Priority.objects.get_or_create(
        value=priority_value, defaults={"name": f"P{priority_value}"}
    )[0]
    return IncidentFactory.create(
        priority=priority, incident_category=category, private=private
    )


@pytest.mark.django_db
class TestInvitedForAllPublicP1Usergroup:
    def test_public_p1_invites_p1_usergroup(
        self, p1_group_member: User, category_group_member: User
    ) -> None:
        incident = _make_incident(
            category_group_member, priority_value=1, private=False
        )

        assert p1_group_member in get_invites_from_slack_for_p1(incident)
        assert p1_group_member in incident.build_invite_list()

    def test_private_p1_does_not_invite_p1_usergroup(
        self, p1_group_member: User, category_group_member: User
    ) -> None:
        incident = _make_incident(category_group_member, priority_value=1, private=True)

        assert list(get_invites_from_slack_for_p1(incident)) == []
        assert p1_group_member not in incident.build_invite_list()

    def test_public_p2_does_not_invite_p1_usergroup(
        self, p1_group_member: User, category_group_member: User
    ) -> None:
        incident = _make_incident(
            category_group_member, priority_value=2, private=False
        )

        assert list(get_invites_from_slack_for_p1(incident)) == []
        assert p1_group_member not in incident.build_invite_list()


@pytest.mark.django_db
class TestPrivateIncidentInvites:
    def test_private_p1_invites_only_its_category_usergroup(
        self, p1_group_member: User, category_group_member: User
    ) -> None:
        incident = _make_incident(category_group_member, priority_value=1, private=True)

        assert set(get_invites_from_slack(incident)) == {category_group_member}
        assert set(incident.build_invite_list()) == {category_group_member}
        assert p1_group_member not in incident.build_invite_list()
