"""Test priority mapping from Impact to JIRA for all priority values including P5."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from django.test import TestCase

from firefighter.incidents.factories import (
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.jira_app.models import JiraUser
from firefighter.raid.signals.incident_created import create_ticket
from firefighter.slack.factories import IncidentChannelFactory


class TestPriorityMapping(TestCase):
    """Test priority mapping from Impact to JIRA including P5 support."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()

        # Create or get priorities P1-P5 (use get_or_create to avoid duplicates)
        self.priority_p1, _ = Priority.objects.get_or_create(
            value=1, defaults={"name": "Critical", "order": 1}
        )
        self.priority_p2, _ = Priority.objects.get_or_create(
            value=2, defaults={"name": "High", "order": 2}
        )
        self.priority_p3, _ = Priority.objects.get_or_create(
            value=3, defaults={"name": "Medium", "order": 3}
        )
        self.priority_p4, _ = Priority.objects.get_or_create(
            value=4, defaults={"name": "Low", "order": 4}
        )
        self.priority_p5, _ = Priority.objects.get_or_create(
            value=5, defaults={"name": "Lowest", "order": 5}
        )

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_p1_mapping(self, mock_get_jira_user, mock_client):
        """Test P1 priority mapping to JIRA."""
        self._test_priority_mapping(self.priority_p1, 1, mock_get_jira_user, mock_client)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_p2_mapping(self, mock_get_jira_user, mock_client):
        """Test P2 priority mapping to JIRA."""
        self._test_priority_mapping(self.priority_p2, 2, mock_get_jira_user, mock_client)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_p3_mapping(self, mock_get_jira_user, mock_client):
        """Test P3 priority mapping to JIRA."""
        self._test_priority_mapping(self.priority_p3, 3, mock_get_jira_user, mock_client)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_p4_mapping(self, mock_get_jira_user, mock_client):
        """Test P4 priority mapping to JIRA."""
        self._test_priority_mapping(self.priority_p4, 4, mock_get_jira_user, mock_client)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_p5_mapping(self, mock_get_jira_user, mock_client):
        """Test P5 priority mapping to JIRA - this should now work with our fix."""
        self._test_priority_mapping(self.priority_p5, 5, mock_get_jira_user, mock_client)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_priority_invalid_value_fallback(self, mock_get_jira_user, mock_client):
        """Test that invalid priority values fall back to P1."""
        # Create a priority with an invalid value (>5)
        invalid_priority, _ = Priority.objects.get_or_create(
            value=6, defaults={"name": "Invalid", "order": 6}
        )
        self._test_priority_mapping(invalid_priority, 1, mock_get_jira_user, mock_client)  # Should fallback to 1

    def _test_priority_mapping(self, priority: Priority, expected_jira_priority: int, mock_get_jira_user, mock_client):
        """Helper method to test priority mapping."""
        # Create a real JiraUser for testing
        jira_user = JiraUser.objects.create(id="test-user-id", user=self.user)
        mock_get_jira_user.return_value = jira_user

        # Mock the create_issue return value (exclude watchers as it's a ManyToMany field)
        mock_client.create_issue.return_value = {
            "id": "123456",
            "key": "TEST-123",
            "assignee": None,
            "reporter": jira_user,  # Return the actual JiraUser object
            "issue_type": "Incident",
            "project_key": "INCIDENT",
            "description": "Test incident",
            "summary": "Test Incident"
        }
        mock_client.get_jira_user_from_jira_id.return_value = jira_user
        mock_client.jira.add_watcher = Mock()
        mock_client.jira.remove_watcher = Mock()
        mock_client.jira.add_simple_link = Mock()

        # Create incident with the specific priority
        incident = IncidentFactory(
            priority=priority,
            created_by=self.user,
            title="Test Incident",
            description="Test incident description"
        )

        # Create incident channel
        channel = IncidentChannelFactory(incident=incident)
        channel.add_bookmark = Mock()
        channel.send_message_and_save = Mock()

        # Call the create_ticket function
        create_ticket(sender=None, incident=incident, channel=channel)

        # Verify that create_issue was called with the expected priority
        mock_client.create_issue.assert_called_once()
        call_kwargs = mock_client.create_issue.call_args[1]

        assert call_kwargs["priority"] == expected_jira_priority
        assert call_kwargs["issuetype"] == "Incident"
        assert call_kwargs["summary"] == "Test Incident"

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_create_ticket_no_issue_id_error(self, mock_get_jira_user, mock_client):
        """Test error handling when create_issue returns no ID."""
        test_user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-user-no-id", user=test_user)
        mock_get_jira_user.return_value = jira_user

        # Mock create_issue to return None ID (error case)
        mock_client.create_issue.return_value = {
            "id": None,  # This should trigger the error
            "key": "TEST-123",
            "summary": "Test Incident"
        }

        incident = IncidentFactory(
            priority=self.priority_p1,
            created_by=test_user,
            title="Test Incident"
        )
        channel = IncidentChannelFactory(incident=incident)

        # Should raise JiraAPIError
        with pytest.raises(JiraAPIError):
            create_ticket(sender=None, incident=incident, channel=channel)

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_create_ticket_jira_user_not_found_error(self, mock_get_jira_user, mock_client):
        """Test error handling when default JIRA user is not found."""
        test_user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-user-not-found", user=test_user)
        mock_get_jira_user.return_value = jira_user

        mock_client.create_issue.return_value = {
            "id": "123456",
            "key": "TEST-123",
            "reporter": jira_user,
            "summary": "Test Incident"
        }

        # Mock get_jira_user_from_jira_id to raise JiraUserNotFoundError
        mock_client.get_jira_user_from_jira_id.side_effect = JiraUserNotFoundError("User not found")
        mock_client.jira.add_watcher = Mock()
        mock_client.jira.remove_watcher = Mock()
        mock_client.jira.add_simple_link = Mock()

        incident = IncidentFactory(
            priority=self.priority_p1,
            created_by=test_user,
            title="Test Incident"
        )
        channel = IncidentChannelFactory(incident=incident)
        channel.add_bookmark = Mock()
        channel.send_message_and_save = Mock()

        # Should complete without error despite the exception
        create_ticket(sender=None, incident=incident, channel=channel)

        # Verify the ticket was still created
        mock_client.create_issue.assert_called_once()

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_create_ticket_add_watcher_error(self, mock_get_jira_user, mock_client):
        """Test error handling when adding watcher fails."""
        test_user = UserFactory()
        default_user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-user-add-watcher", user=test_user)
        default_jira_user = JiraUser.objects.create(id="default-user-add", user=default_user)
        mock_get_jira_user.return_value = jira_user

        mock_client.create_issue.return_value = {
            "id": "123456",
            "key": "TEST-123",
            "reporter": jira_user,
            "summary": "Test Incident"
        }
        mock_client.get_jira_user_from_jira_id.return_value = default_jira_user

        # Mock add_watcher to raise JiraAPIError
        mock_client.jira.add_watcher.side_effect = JiraAPIError("Cannot add watcher")
        mock_client.jira.remove_watcher = Mock()
        mock_client.jira.add_simple_link = Mock()

        incident = IncidentFactory(
            priority=self.priority_p1,
            created_by=test_user,
            title="Test Incident"
        )
        channel = IncidentChannelFactory(incident=incident)
        channel.add_bookmark = Mock()
        channel.send_message_and_save = Mock()

        # Should complete without error despite the exception
        create_ticket(sender=None, incident=incident, channel=channel)

        # Verify remove_watcher was called as fallback
        mock_client.jira.remove_watcher.assert_called_once()

    @patch("firefighter.raid.signals.incident_created.client")
    @patch("firefighter.raid.signals.incident_created.get_jira_user_from_user")
    def test_create_ticket_remove_watcher_error(self, mock_get_jira_user, mock_client):
        """Test error handling when removing default watcher fails."""
        test_user = UserFactory()
        default_user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-user-remove-watcher", user=test_user)
        default_jira_user = JiraUser.objects.create(id="default-user-remove", user=default_user)
        mock_get_jira_user.return_value = jira_user

        mock_client.create_issue.return_value = {
            "id": "123456",
            "key": "TEST-123",
            "reporter": jira_user,
            "summary": "Test Incident"
        }
        mock_client.get_jira_user_from_jira_id.return_value = default_jira_user

        # Mock both add_watcher and remove_watcher to raise JiraAPIError
        mock_client.jira.add_watcher.side_effect = JiraAPIError("Cannot add watcher")
        mock_client.jira.remove_watcher.side_effect = JiraAPIError("Cannot remove watcher")
        mock_client.jira.add_simple_link = Mock()

        incident = IncidentFactory(
            priority=self.priority_p1,
            created_by=test_user,
            title="Test Incident"
        )
        channel = IncidentChannelFactory(incident=incident)
        channel.add_bookmark = Mock()
        channel.send_message_and_save = Mock()

        # Should complete without error despite both exceptions
        create_ticket(sender=None, incident=incident, channel=channel)

        # Verify both operations were attempted
        mock_client.jira.add_watcher.assert_called_once()
        mock_client.jira.remove_watcher.assert_called_once()
