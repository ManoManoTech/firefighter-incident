"""Tests for Jira webhook serializers with sync functionality."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.client import SlackNotificationError
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import JiraTicket
from firefighter.raid.serializers import JiraWebhookUpdateSerializer


@pytest.mark.django_db
class TestJiraWebhookUpdateSerializerWithSync:
    """Test JiraWebhookUpdateSerializer with sync functionality."""

    def setup_method(self):
        """Set up test data."""
        self.incident = IncidentFactory()
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-user-999", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=99999,
            key="INC-999",
            summary="Test ticket",
            description="Test description",
            reporter=self.jira_user,
            incident=self.incident,
        )

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_triggers_sync(
        self, mock_slack_alert, mock_handle_webhook
    ):
        """Test that webhook update triggers sync to Impact."""
        mock_handle_webhook.return_value = True
        mock_slack_alert.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
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
        mock_slack_alert.assert_called_once()

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_sync_failure_still_alerts_slack(
        self, mock_slack_alert, mock_handle_webhook
    ):
        """Test that sync failure doesn't prevent Slack alert."""
        mock_handle_webhook.return_value = False  # Sync fails
        mock_slack_alert.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
                "changelog": {
                    "items": [
                        {
                            "field": "Priority",
                            "fromString": "Medium",
                            "toString": "High",
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
        mock_slack_alert.assert_called_once()

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_non_tracked_field_no_slack(
        self, mock_slack_alert, mock_handle_webhook
    ):
        """Test that non-tracked field changes still sync but don't alert Slack."""
        mock_handle_webhook.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
                "changelog": {
                    "items": [
                        {
                            "field": "labels",  # Not in tracked fields for Slack
                            "fromString": "label1",
                            "toString": "label2",
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
        mock_slack_alert.assert_not_called()

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_slack_alert_failure_raises_error(
        self, mock_slack_alert, mock_handle_webhook
    ):
        """Test that Slack alert failure raises an error."""
        mock_handle_webhook.return_value = True
        mock_slack_alert.return_value = False  # Slack alert fails

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
                "changelog": {
                    "items": [
                        {
                            "field": "status",
                            "fromString": "Open",
                            "toString": "Closed",
                        }
                    ]
                },
                "user": {"displayName": "Test User"},
                "webhookEvent": "jira:issue_updated",
            }
        )

        assert serializer.is_valid()

        with pytest.raises(SlackNotificationError):
            serializer.save()

    def test_webhook_update_invalid_event(self):
        """Test that invalid webhook event is rejected."""
        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
                "changelog": {"items": []},
                "user": {"displayName": "Test User"},
                "webhookEvent": "jira:invalid_event",
            }
        )

        assert not serializer.is_valid()
        assert "webhookEvent" in serializer.errors

    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_multiple_field_changes(
        self, mock_slack_alert, mock_handle_webhook
    ):
        """Test webhook with multiple field changes."""
        mock_handle_webhook.return_value = True
        mock_slack_alert.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {
                    "id": "99999",
                    "key": "INC-999",
                    "fields": {
                        "summary": "Updated title",
                        "description": "Updated description",
                        "status": {"name": "In Progress"},
                    },
                },
                "changelog": {
                    "items": [
                        {
                            "field": "status",
                            "fromString": "Open",
                            "toString": "In Progress",
                        },
                        {
                            "field": "summary",
                            "fromString": "Old title",
                            "toString": "Updated title",
                        },
                    ]
                },
                "user": {"displayName": "Test User"},
                "webhookEvent": "jira:issue_updated",
            }
        )

        assert serializer.is_valid()
        result = serializer.save()

        assert result is True
        # handle_jira_webhook_update should be called once with all changes
        mock_handle_webhook.assert_called_once()
        # alert_slack_update_ticket should be called for the first tracked field
        mock_slack_alert.assert_called_once()

    @patch("firefighter.raid.serializers.logger")
    @patch("firefighter.raid.serializers.handle_jira_webhook_update")
    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_webhook_update_logs_sync_failure(
        self, mock_slack_alert, mock_handle_webhook, mock_logger
    ):
        """Test that sync failures are logged."""
        mock_handle_webhook.return_value = False
        mock_slack_alert.return_value = True

        serializer = JiraWebhookUpdateSerializer(
            data={
                "issue": {"id": "99999", "key": "INC-999", "fields": {}},
                "changelog": {
                    "items": [
                        {
                            "field": "Priority",
                            "fromString": "Low",
                            "toString": "High",
                        }
                    ]
                },
                "user": {"displayName": "Test User"},
                "webhookEvent": "jira:issue_updated",
            }
        )

        assert serializer.is_valid()
        serializer.save()

        mock_logger.warning.assert_called_once_with(
            "Failed to sync Jira changes to Impact incident"
        )
