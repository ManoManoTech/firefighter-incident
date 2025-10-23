"""Tests for incident priority downgrade signal handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Priority
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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

        # Mock the send_message_ephemeral method
        mock_send = mocker.patch.object(conversation, "send_message_ephemeral")

        # Downgrade from P2 to P4
        incident.create_incident_update(
            created_by=user, priority_id=p4.id, message="Downgrading to P4"
        )

        # Verify the downgrade hint message was sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args is not None
        # Check that the message is about the incident not needing an incident channel
        message = call_args.kwargs["message"]
        message_text = message.get_text().lower()
        assert "might not need an incident channel" in message_text or "p4" in message_text or "p5" in message_text

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

        # Mock the send_message_ephemeral method
        mock_send = mocker.patch.object(conversation, "send_message_ephemeral")

        # Update from P1 to P3 (both critical)
        incident.create_incident_update(
            created_by=user, priority_id=p3.id, message="Updating to P3"
        )

        # Verify NO downgrade hint was sent
        mock_send.assert_not_called()

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

        # Mock the send_message_ephemeral method
        mock_send = mocker.patch.object(conversation, "send_message_ephemeral")

        # Update from P4 to P5 (both normal)
        incident.create_incident_update(
            created_by=user, priority_id=p5.id, message="Updating to P5"
        )

        # Verify NO downgrade hint was sent
        mock_send.assert_not_called()

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

        # Mock the send_message_ephemeral method
        mock_send = mocker.patch.object(conversation, "send_message_ephemeral")

        # Upgrade from P5 to P2
        incident.create_incident_update(
            created_by=user, priority_id=p2.id, message="Escalating to P2"
        )

        # Verify NO downgrade hint was sent (this is an upgrade, not a downgrade)
        mock_send.assert_not_called()
