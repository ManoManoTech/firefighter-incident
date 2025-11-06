"""Tests for enhanced Slack integration with Jira webhook updates."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.models import JiraUser
from firefighter.raid.forms import (
    alert_slack_update_ticket,
    send_message_to_incident_channel,
)
from firefighter.raid.messages import SlackMessageRaidModifiedIssue
from firefighter.raid.models import JiraTicket
from firefighter.raid.serializers import JiraWebhookUpdateSerializer


@pytest.mark.django_db
class TestSlackIncidentChannelIntegration:
    """Test Slack incident channel integration for Jira updates."""

    def setup_method(self):
        """Set up test data."""
        self.incident = IncidentFactory()
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-user-slack", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=88888,
            key="INC-SLACK",
            summary="Test Slack integration",
            description="Test description",
            reporter=self.jira_user,
            incident=self.incident,
        )

    @patch("firefighter.raid.forms.JiraTicket.objects.select_related")
    def test_send_message_to_incident_channel_critical_field_status(self, mock_select_related):
        """Test that status changes are sent to incident channel."""
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="status",
            jira_field_from="Open",
            jira_field_to="In Progress",
        )

        # Mock incident channel
        mock_channel = MagicMock()
        mock_channel.name = "incident-123"

        # Mock incident with channel
        mock_incident = MagicMock()
        mock_incident.id = 1
        mock_incident.incidentchannel = mock_channel

        # Mock jira ticket with mocked incident
        mock_jira_ticket = MagicMock()
        mock_jira_ticket.key = "INC-SLACK"
        mock_jira_ticket.incident = mock_incident

        # Mock the ORM query chain
        mock_manager = MagicMock()
        mock_manager.get.return_value = mock_jira_ticket
        mock_select_related.return_value = mock_manager

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="status",
            message=message
        )

        assert result is True
        mock_channel.send_message_and_save.assert_called_once_with(message)

    @patch("firefighter.raid.forms.JiraTicket.objects.select_related")
    def test_send_message_to_incident_channel_critical_field_priority(self, mock_select_related):
        """Test that priority changes are sent to incident channel."""
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="Priority",
            jira_field_from="Medium",
            jira_field_to="High",
        )

        # Mock incident channel
        mock_channel = MagicMock()
        mock_channel.name = "incident-123"

        # Mock incident with channel
        mock_incident = MagicMock()
        mock_incident.id = 1
        mock_incident.incidentchannel = mock_channel

        # Mock jira ticket with mocked incident
        mock_jira_ticket = MagicMock()
        mock_jira_ticket.key = "INC-SLACK"
        mock_jira_ticket.incident = mock_incident

        # Mock the ORM query chain
        mock_manager = MagicMock()
        mock_manager.get.return_value = mock_jira_ticket
        mock_select_related.return_value = mock_manager

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="Priority",
            message=message
        )

        assert result is True
        mock_channel.send_message_and_save.assert_called_once_with(message)

    def test_send_message_to_incident_channel_non_critical_field_skipped(self):
        """Test that non-critical field changes are not sent to incident channel."""
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="description",
            jira_field_from="Old description",
            jira_field_to="New description",
        )

        # Mock incident channel
        mock_channel = MagicMock()
        self.incident.incidentchannel = mock_channel

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="description",
            message=message
        )

        assert result is True
        mock_channel.send_message_and_save.assert_not_called()

    def test_send_message_to_incident_channel_no_incident(self):
        """Test that tickets without incidents don't send to channel."""
        self.jira_ticket.incident = None
        self.jira_ticket.save()

        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="status",
            jira_field_from="Open",
            jira_field_to="Closed",
        )

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="status",
            message=message
        )

        assert result is True  # Success but no action taken

    def test_send_message_to_incident_channel_no_slack_channel(self):
        """Test that incidents without Slack channels don't fail."""
        # Incident exists but has no incidentchannel attribute
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="status",
            jira_field_from="Open",
            jira_field_to="Closed",
        )

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="status",
            message=message
        )

        assert result is True  # Success but no action taken

    def test_send_message_to_incident_channel_ticket_not_found(self):
        """Test that non-existent tickets return False."""
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="NONEXISTENT",
            jira_author_name="Test User",
            jira_field_modified="status",
            jira_field_from="Open",
            jira_field_to="Closed",
        )

        result = send_message_to_incident_channel(
            jira_ticket_id=99999,  # Non-existent ID
            jira_field_modified="status",
            message=message
        )

        assert result is False

    @patch("firefighter.raid.forms.send_message_to_incident_channel")
    @patch("firefighter.raid.forms.send_message_to_watchers")
    def test_enhanced_alert_slack_update_ticket_integration(
        self, mock_send_to_watchers, mock_send_to_channel
    ):
        """Test that the enhanced alert function calls both notification methods."""
        mock_send_to_watchers.return_value = True
        mock_send_to_channel.return_value = True

        result = alert_slack_update_ticket(
            jira_ticket_id=88888,
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="status",
            jira_field_from="Open",
            jira_field_to="In Progress",
        )

        assert result is True
        mock_send_to_watchers.assert_called_once()
        mock_send_to_channel.assert_called_once()

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.forms.send_message_to_incident_channel")
    @patch("firefighter.raid.forms.send_message_to_watchers")
    def test_webhook_serializer_uses_enhanced_slack_integration(
        self, mock_send_to_watchers, mock_send_to_channel, mock_handle_webhook
    ):
        """Test that webhook serializer uses the enhanced Slack integration."""
        mock_handle_webhook.return_value = True
        mock_send_to_watchers.return_value = True
        mock_send_to_channel.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "88888", "key": "INC-SLACK", "fields": {}},
                "changelog": {
                    "items": [
                        {
                            "field": "status",
                            "fromString": "Open",
                            "toString": "In Progress",
                        }
                    ]
                },
                "user": {"displayName": "Test User"},
                "webhookEvent": "jira:issue_updated",
            }
        )

        assert serializer.is_valid()
        result = serializer.save()

        assert result is True
        mock_handle_webhook.assert_called_once()
        mock_send_to_watchers.assert_called_once()
        mock_send_to_channel.assert_called_once()

    @patch("firefighter.raid.forms.JiraTicket.objects.select_related")
    def test_send_message_channel_error_handling(self, mock_select_related):
        """Test that channel send errors are handled gracefully."""
        message = SlackMessageRaidModifiedIssue(
            jira_ticket_key="INC-SLACK",
            jira_author_name="Test User",
            jira_field_modified="Priority",
            jira_field_from="Low",
            jira_field_to="High",
        )

        # Mock incident channel that raises an exception
        mock_channel = MagicMock()
        mock_channel.name = "incident-123"
        mock_channel.send_message_and_save.side_effect = Exception("Slack API error")

        # Mock incident with channel
        mock_incident = MagicMock()
        mock_incident.id = 1
        mock_incident.incidentchannel = mock_channel

        # Mock jira ticket with mocked incident
        mock_jira_ticket = MagicMock()
        mock_jira_ticket.key = "INC-SLACK"
        mock_jira_ticket.incident = mock_incident

        # Mock the ORM query chain
        mock_manager = MagicMock()
        mock_manager.get.return_value = mock_jira_ticket
        mock_select_related.return_value = mock_manager

        result = send_message_to_incident_channel(
            jira_ticket_id=88888,
            jira_field_modified="Priority",
            message=message
        )

        assert result is False
        mock_channel.send_message_and_save.assert_called_once_with(message)
