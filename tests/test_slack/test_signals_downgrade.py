"""Tests for incident priority downgrade signal handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Priority
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import (
    COMMANDER_ROLE_SLUG,
    IncidentRoleType,
)
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.messages.slack_messages import SlackMessageIncidentDowngradeHint

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


def _hints(mock_send: MagicMock) -> list[SlackMessageIncidentDowngradeHint]:
    """The downgrade hints posted, ignoring the other messages of the update (status, etc.)."""
    return [
        call.args[0]
        for call in mock_send.call_args_list
        if isinstance(call.args[0], SlackMessageIncidentDowngradeHint)
    ]


@pytest.mark.django_db
class TestIncidentDowngradeSignal:
    """Test the incident_updated_check_dowmgrade_handler signal."""

    @staticmethod
    def test_downgrade_hint_shown_for_critical_to_normal(mocker: MockerFixture) -> None:
        """Test that downgrade hint is shown when downgrading from P1/P2/P3 to P4/P5."""
        # Create a user with a Slack user
        user = UserFactory.build()
        user.save()
        slack_user = SlackUserFactory.build(user=user)
        slack_user.save()

        # Get priorities from DB
        p2 = Priority.objects.get(name="P2")
        p4 = Priority.objects.get(name="P4")

        # Create an incident with P2 priority
        incident = IncidentFactory.build(priority=p2, created_by=user)
        incident.save()

        # Create an incident channel (conversation) for this incident
        conversation = IncidentChannelFactory.build(incident=incident)
        conversation.save()

        # Mock the send_message_and_save method
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        # Downgrade from P2 to P4
        incident.create_incident_update(
            created_by=user, priority_id=p4.id, message="Downgrading to P4"
        )

        # The hint is posted publicly, and falls back to the author when nobody holds command
        (message,) = _hints(mock_send)
        assert message.decider is not None
        assert message.decider.slack_id == slack_user.slack_id
        assert f"<@{slack_user.slack_id}>" in message.get_text()
        assert "P4" in message.get_text()

    @staticmethod
    def test_no_hint_when_staying_in_critical_range(mocker: MockerFixture) -> None:
        """Test that no hint is shown when changing priority within critical range (P1/P2/P3)."""
        # Create a user
        user = UserFactory.build()
        user.save()

        # Get priorities from DB
        p1 = Priority.objects.get(name="P1")
        p3 = Priority.objects.get(name="P3")

        # Create an incident with P1 priority
        incident = IncidentFactory.build(priority=p1, created_by=user)
        incident.save()

        # Create an incident channel (conversation) for this incident
        conversation = IncidentChannelFactory.build(incident=incident)
        conversation.save()

        # Mock the send_message_and_save method
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        # Update from P1 to P3 (both critical)
        incident.create_incident_update(
            created_by=user, priority_id=p3.id, message="Updating to P3"
        )

        # Verify NO downgrade hint was sent
        assert _hints(mock_send) == []

    @staticmethod
    def test_no_hint_when_staying_in_normal_range(mocker: MockerFixture) -> None:
        """Test that no hint is shown when changing priority within normal range (P4/P5)."""
        # Create a user
        user = UserFactory.build()
        user.save()

        # Get priorities from DB
        p4 = Priority.objects.get(name="P4")
        p5 = Priority.objects.get(name="P5")

        # Create an incident with P4 priority
        incident = IncidentFactory.build(priority=p4, created_by=user)
        incident.save()

        # Create an incident channel (conversation) for this incident
        conversation = IncidentChannelFactory.build(incident=incident)
        conversation.save()

        # Mock the send_message_and_save method
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        # Update from P4 to P5 (both normal)
        incident.create_incident_update(
            created_by=user, priority_id=p5.id, message="Updating to P5"
        )

        # Verify NO downgrade hint was sent
        assert _hints(mock_send) == []

    @staticmethod
    def test_no_hint_when_upgrading_from_normal_to_critical(mocker: MockerFixture) -> None:
        """Test that no hint is shown when upgrading from P4/P5 to P1/P2/P3."""
        # Create a user
        user = UserFactory.build()
        user.save()

        # Get priorities from DB
        p5 = Priority.objects.get(name="P5")
        p2 = Priority.objects.get(name="P2")

        # Create an incident with P5 priority
        incident = IncidentFactory.build(priority=p5, created_by=user)
        incident.save()

        # Create an incident channel (conversation) for this incident
        conversation = IncidentChannelFactory.build(incident=incident)
        conversation.save()

        # Mock the send_message_and_save method
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        # Upgrade from P5 to P2
        incident.create_incident_update(
            created_by=user, priority_id=p2.id, message="Escalating to P2"
        )

        # Verify NO downgrade hint was sent (this is an upgrade, not a downgrade)
        assert _hints(mock_send) == []

    @staticmethod
    def test_downgrade_hint_mentions_the_commander(mocker: MockerFixture) -> None:
        """The decision belongs to the Commander, even when someone else downgraded."""
        author = UserFactory.create()
        SlackUserFactory.create(user=author)
        commander = UserFactory.create()
        commander_slack = SlackUserFactory.create(user=commander)

        incident = IncidentFactory.create(
            priority=Priority.objects.get(name="P3"), created_by=author
        )
        IncidentRole.objects.create(
            incident=incident,
            user=commander,
            role_type=IncidentRoleType.objects.get(slug=COMMANDER_ROLE_SLUG),
        )
        conversation = IncidentChannelFactory.create(incident=incident)
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        incident.create_incident_update(
            created_by=author,
            priority_id=Priority.objects.get(name="P5").id,
            message="Downgrading to P5",
        )

        (message,) = _hints(mock_send)
        assert message.decider is not None
        assert message.decider.slack_id == commander_slack.slack_id
        blocks_text = " ".join(
            block.text.text for block in message.get_blocks() if getattr(block, "text", None)
        )
        assert f"<@{commander_slack.slack_id}>, as Incident Commander the decision is yours" in blocks_text
        assert "You may keep this channel if it helps coordinate the response" in blocks_text

    @staticmethod
    def test_downgrade_hint_posted_without_anyone_to_mention(mocker: MockerFixture) -> None:
        """Without a Commander nor a Slack author, the hint is still posted, addressed to the role."""
        author = UserFactory.create()
        incident = IncidentFactory.create(
            priority=Priority.objects.get(name="P2"), created_by=author
        )
        conversation = IncidentChannelFactory.create(incident=incident)
        mock_send = mocker.patch.object(conversation, "send_message_and_save")

        incident.create_incident_update(
            created_by=author,
            priority_id=Priority.objects.get(name="P4").id,
            message="Downgrading to P4",
        )

        (message,) = _hints(mock_send)
        assert message.decider is None
        assert "Incident Commander, please decide" in message.get_text()
