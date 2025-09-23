"""Test raid serializers, especially uncovered functionality."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
from rest_framework import serializers

from firefighter.incidents.factories import UserFactory
from firefighter.incidents.models.user import User
from firefighter.jira_app.client import (
    JiraAPIError,
    JiraUserNotFoundError,
    SlackNotificationError,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import JiraTicket
from firefighter.raid.serializers import (
    IgnoreEmptyStringListField,
    JiraWebhookCommentSerializer,
    JiraWebhookUpdateSerializer,
    LandbotIssueRequestSerializer,
    get_reporter_user_from_email,
    validate_no_spaces,
)
from firefighter.slack.factories import SlackUserFactory


class TestIgnoreEmptyStringListField(TestCase):
    """Test IgnoreEmptyStringListField custom field."""

    def setUp(self):
        """Set up test field."""
        self.field = IgnoreEmptyStringListField(child=serializers.CharField())

    def test_valid_list_with_empty_strings(self):
        """Test that empty strings are filtered out."""
        data = ["valid", "", "another", ""]
        result = self.field.to_internal_value(data)
        assert result == ["valid", "another"]

    def test_valid_list_no_empty_strings(self):
        """Test list without empty strings."""
        data = ["valid", "another"]
        result = self.field.to_internal_value(data)
        assert result == ["valid", "another"]

    def test_empty_list(self):
        """Test empty list."""
        data = []
        result = self.field.to_internal_value(data)
        assert result == []

    def test_list_with_only_empty_strings(self):
        """Test list with only empty strings."""
        data = ["", "", ""]
        result = self.field.to_internal_value(data)
        assert result == []

    def test_invalid_non_list_data(self):
        """Test that non-list data raises ValidationError."""
        with pytest.raises(serializers.ValidationError) as exc_info:
            self.field.to_internal_value("not a list")
        assert 'Expected a list but got type "str"' in str(exc_info.value)


class TestValidateNoSpaces(TestCase):
    """Test validate_no_spaces function."""

    def test_valid_string_no_spaces(self):
        """Test string without spaces passes validation."""
        # Should not raise any exception
        validate_no_spaces("validstring")
        validate_no_spaces("valid-string")
        validate_no_spaces("valid_string")

    def test_invalid_string_with_spaces(self):
        """Test string with spaces raises ValidationError."""
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_no_spaces("invalid string")
        assert "The string cannot contain spaces" in str(exc_info.value)

    def test_string_with_multiple_spaces(self):
        """Test string with multiple spaces raises ValidationError."""
        with pytest.raises(serializers.ValidationError):
            validate_no_spaces("invalid string with spaces")


class TestGetReporterUserFromEmail(TestCase):
    """Test get_reporter_user_from_email function."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(email="test@manomano.com")

    @patch("firefighter.raid.serializers.jira_client")
    def test_existing_user_found(self, mock_jira_client):
        """Test when user and JIRA user are found."""
        # Create JiraUser
        jira_user = JiraUser.objects.create(id="jira-123", user=self.user)
        mock_jira_client.get_jira_user_from_user.return_value = jira_user

        reporter_user, reporter, user_domain = get_reporter_user_from_email("test@manomano.com")

        assert reporter_user == self.user
        assert reporter == jira_user
        assert user_domain == "manomano.com"
        mock_jira_client.get_jira_user_from_user.assert_called_once_with(self.user)

    @patch("firefighter.raid.serializers.jira_client")
    @patch("firefighter.raid.serializers.SlackUser")
    def test_user_not_found_with_slack_fallback(self, mock_slack_user, mock_jira_client):
        """Test when user is not found but Slack user exists."""
        # Setup mocks
        slack_user = SlackUserFactory()
        mock_slack_user.objects.upsert_by_email.return_value = slack_user.user

        default_jira_user = JiraUser.objects.create(id="default-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = default_jira_user

        reporter_user, reporter, user_domain = get_reporter_user_from_email("nonexistent@example.com")

        assert reporter_user == slack_user.user
        assert reporter == default_jira_user
        assert user_domain == "example.com"

    @patch("firefighter.raid.serializers.jira_client")
    @patch("firefighter.raid.serializers.SlackUser")
    @patch("firefighter.raid.serializers.JIRA_USER_IDS", {"example.com": "domain-specific-123"})
    def test_user_not_found_with_domain_specific_jira_user(self, mock_slack_user, mock_jira_client):
        """Test when user is not found but domain has specific JIRA user."""
        # Setup mocks
        mock_slack_user.objects.upsert_by_email.return_value = None

        domain_jira_user = JiraUser.objects.create(id="domain-specific-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = domain_jira_user

        reporter_user, reporter, user_domain = get_reporter_user_from_email("test@example.com")

        assert reporter_user == domain_jira_user.user
        assert reporter == domain_jira_user
        assert user_domain == "example.com"
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once_with("domain-specific-123")

    @patch("firefighter.raid.serializers.jira_client")
    def test_jira_user_not_found_exception(self, mock_jira_client):
        """Test when JiraUserNotFoundError is raised."""
        mock_jira_client.get_jira_user_from_user.side_effect = JiraUserNotFoundError("User not found")

        default_jira_user = JiraUser.objects.create(id="default-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = default_jira_user

        reporter_user, reporter, user_domain = get_reporter_user_from_email("test@manomano.com")

        assert reporter_user == self.user
        assert reporter == default_jira_user
        assert user_domain == "manomano.com"


class TestLandbotIssueRequestSerializer(TestCase):
    """Test LandbotIssueRequestSerializer functionality."""

    def test_validate_environments_with_empty_value(self):
        """Test validate_environments with empty/None value."""
        serializer = LandbotIssueRequestSerializer()

        # Test with None
        result = serializer.validate_environments(None)
        assert result == ["-"]  # Default value

        # Test with empty list
        result = serializer.validate_environments([])
        assert result == ["-"]  # Default value

    def test_validate_environments_with_valid_value(self):
        """Test validate_environments with valid value."""
        serializer = LandbotIssueRequestSerializer()

        environments = ["PRD", "STG"]
        result = serializer.validate_environments(environments)
        assert result == environments

    @patch("firefighter.raid.serializers.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.serializers.get_reporter_user_from_email")
    @patch("firefighter.raid.serializers.jira_client")
    def test_create_with_attachments_error(self, mock_jira_client, mock_get_reporter, mock_alert_slack):
        """Test create method when JIRA returns no issue ID."""
        # Setup mocks
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-123", user=user)
        mock_get_reporter.return_value = (user, jira_user, "example.com")
        mock_alert_slack.return_value = None

        # Mock create_issue to return None ID (error case)
        mock_jira_client.create_issue.return_value = {"id": None, "key": "TEST-123"}

        serializer = LandbotIssueRequestSerializer()
        validated_data = {
            "reporter_email": "test@example.com",
            "issue_type": "Incident",
            "summary": "Test Issue",
            "description": "Test Description",
            "labels": ["test"],
            "priority": 1,
            "seller_contract_id": "123",
            "zoho": "456",
            "platform": "ES",
            "incident_category": "test",
            "business_impact": "High",
            "environments": ["PRD"],
            "suggested_team_routing": "TEAM1",
            "project": "SBI",
            "attachments": None,
        }

        with pytest.raises(JiraAPIError):
            serializer.create(validated_data)

    @patch("firefighter.raid.serializers.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.serializers.get_reporter_user_from_email")
    @patch("firefighter.raid.serializers.jira_client")
    def test_create_with_attachments(self, mock_jira_client, mock_get_reporter, mock_alert_slack):
        """Test create method with attachments."""
        # Setup mocks
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-123", user=user)
        mock_get_reporter.return_value = (user, jira_user, "example.com")
        mock_alert_slack.return_value = None

        mock_jira_client.create_issue.return_value = {
            "id": "12345",
            "key": "TEST-123",
            "summary": "Test Issue",
            "reporter": jira_user,
        }
        mock_jira_client.add_attachments_to_issue = Mock()

        serializer = LandbotIssueRequestSerializer()
        validated_data = {
            "reporter_email": "test@example.com",
            "issue_type": "Incident",
            "summary": "Test Issue",
            "description": "Test Description",
            "labels": ["test"],
            "priority": 1,
            "seller_contract_id": "123",
            "zoho": "456",
            "platform": "ES",
            "incident_category": "test",
            "business_impact": "High",
            "environments": ["PRD"],
            "suggested_team_routing": "TEAM1",
            "project": "SBI",
            "attachments": "['file1.jpg', 'file2.pdf', '']",  # String with empty attachment
        }

        result = serializer.create(validated_data)

        # Verify attachments were processed and empty strings filtered
        mock_jira_client.add_attachments_to_issue.assert_called_once_with(
            "12345", ["file1.jpg", "file2.pdf"]
        )
        assert isinstance(result, JiraTicket)
        mock_alert_slack.assert_called_once()

    @patch("firefighter.raid.serializers.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.serializers.get_reporter_user_from_email")
    @patch("firefighter.raid.serializers.jira_client")
    def test_create_external_user_description(self, mock_jira_client, mock_get_reporter, mock_alert_slack):
        """Test create method adds email to description for external users."""
        # Setup mocks - external domain
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-123", user=user)
        mock_get_reporter.return_value = (user, jira_user, "external.com")
        mock_alert_slack.return_value = None

        mock_jira_client.create_issue.return_value = {
            "id": "12345",
            "key": "TEST-123",
            "summary": "Test Issue",
            "reporter": jira_user,
        }

        serializer = LandbotIssueRequestSerializer()
        validated_data = {
            "reporter_email": "test@external.com",
            "issue_type": "Incident",
            "summary": "Test Issue",
            "description": "Test Description",
            "labels": [],
            "priority": 1,
            "seller_contract_id": None,
            "zoho": None,
            "platform": "ES",
            "incident_category": None,
            "business_impact": None,
            "environments": ["PRD"],
            "suggested_team_routing": "TEAM1",
            "project": "SBI",
            "attachments": None,
        }

        result = serializer.create(validated_data)

        # Verify description includes reporter email for external users
        create_call = mock_jira_client.create_issue.call_args[1]
        assert "Reporter email test@external.com" in create_call["description"]
        assert isinstance(result, JiraTicket)
        mock_alert_slack.assert_called_once_with(
            result, reporter_user=user, reporter_email="test@external.com"
        )


class TestJiraWebhookUpdateSerializer(TestCase):
    """Test JiraWebhookUpdateSerializer functionality."""

    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_create_with_tracked_field(self, mock_alert):
        """Test create method with a tracked field change."""
        mock_alert.return_value = True

        serializer = JiraWebhookUpdateSerializer()
        validated_data = {
            "issue": {"id": "12345", "key": "TEST-123"},
            "changelog": {
                "items": [
                    {
                        "field": "Priority",
                        "fromString": "High",
                        "toString": "Critical"
                    }
                ]
            },
            "user": {"displayName": "John Doe"},
            "webhookEvent": "jira:issue_updated"
        }

        result = serializer.create(validated_data)
        assert result is True
        mock_alert.assert_called_once()

    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_create_with_untracked_field(self, mock_alert):
        """Test create method with an untracked field change."""
        serializer = JiraWebhookUpdateSerializer()
        validated_data = {
            "issue": {"id": "12345", "key": "TEST-123"},
            "changelog": {
                "items": [
                    {
                        "field": "labels",  # Not tracked
                        "fromString": "old",
                        "toString": "new"
                    }
                ]
            },
            "user": {"displayName": "John Doe"},
            "webhookEvent": "jira:issue_updated"
        }

        result = serializer.create(validated_data)
        assert result is True
        mock_alert.assert_not_called()

    @patch("firefighter.raid.serializers.alert_slack_update_ticket")
    def test_create_slack_notification_error(self, mock_alert):
        """Test create method when Slack notification fails."""
        mock_alert.return_value = False

        serializer = JiraWebhookUpdateSerializer()
        validated_data = {
            "issue": {"id": "12345", "key": "TEST-123"},
            "changelog": {
                "items": [
                    {
                        "field": "status",
                        "fromString": "Open",
                        "toString": "Closed"
                    }
                ]
            },
            "user": {"displayName": "John Doe"},
            "webhookEvent": "jira:issue_updated"
        }

        with pytest.raises(SlackNotificationError):
            serializer.create(validated_data)

    def test_update_not_implemented(self):
        """Test that update method raises NotImplementedError."""
        serializer = JiraWebhookUpdateSerializer()
        with pytest.raises(NotImplementedError):
            serializer.update(None, {})


class TestJiraWebhookCommentSerializer(TestCase):
    """Test JiraWebhookCommentSerializer functionality."""

    @patch("firefighter.raid.serializers.alert_slack_comment_ticket")
    def test_create_successful(self, mock_alert):
        """Test create method successful case."""
        mock_alert.return_value = True

        serializer = JiraWebhookCommentSerializer()
        validated_data = {
            "issue": {"id": "12345", "key": "TEST-123"},
            "comment": {
                "author": {"displayName": "John Doe"},
                "body": "This is a test comment"
            },
            "webhookEvent": "comment_created"
        }

        result = serializer.create(validated_data)
        assert result is True
        mock_alert.assert_called_once_with(
            webhook_event="comment_created",
            jira_ticket_id="12345",
            jira_ticket_key="TEST-123",
            author_jira_name="John Doe",
            comment="This is a test comment"
        )

    @patch("firefighter.raid.serializers.alert_slack_comment_ticket")
    def test_create_slack_notification_error(self, mock_alert):
        """Test create method when Slack notification fails."""
        mock_alert.return_value = False

        serializer = JiraWebhookCommentSerializer()
        validated_data = {
            "issue": {"id": "12345", "key": "TEST-123"},
            "comment": {
                "author": {"displayName": "John Doe"},
                "body": "This is a test comment"
            },
            "webhookEvent": "comment_updated"
        }

        with pytest.raises(SlackNotificationError):
            serializer.create(validated_data)

    def test_update_not_implemented(self):
        """Test that update method raises NotImplementedError."""
        serializer = JiraWebhookCommentSerializer()
        with pytest.raises(NotImplementedError):
            serializer.update(None, {})


@pytest.mark.django_db
class TestGetReporterUserFromEmailAdditional:
    """Additional tests for get_reporter_user_from_email to reach 100% coverage."""

    @patch("firefighter.raid.serializers.jira_client")
    @patch("firefighter.raid.serializers.SlackUser")
    def test_user_does_not_exist_no_slack_fallback(self, mock_slack_user, mock_jira_client):
        """Test when User.DoesNotExist and no Slack user exists."""
        # Setup mocks
        mock_slack_user.objects.upsert_by_email.return_value = None

        default_jira_user = JiraUser.objects.create(id="default-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = default_jira_user

        reporter_user, reporter, user_domain = get_reporter_user_from_email("test@example.com")

        assert reporter_user == default_jira_user.user
        assert reporter == default_jira_user
        assert user_domain == "example.com"

    @patch("firefighter.raid.serializers.jira_client")
    @patch("firefighter.raid.serializers.SlackUser")
    def test_slack_user_exists_but_reporter_user_tmp_is_none(self, mock_slack_user, mock_jira_client):
        """Test when Slack upsert returns None and we use default JIRA user."""
        # Setup mocks - simulate User.DoesNotExist
        mock_slack_user.objects.upsert_by_email.return_value = None

        default_jira_user = JiraUser.objects.create(id="default-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = default_jira_user

        with patch("firefighter.raid.serializers.User.objects.get", side_effect=User.DoesNotExist):
            reporter_user, reporter, user_domain = get_reporter_user_from_email("test@example.com")

        # Should use default JIRA user's user since reporter_user_tmp is None
        assert reporter_user == default_jira_user.user
        assert reporter == default_jira_user
        assert user_domain == "example.com"

    @patch("firefighter.raid.serializers.jira_client")
    @patch("firefighter.raid.serializers.SlackUser")
    @patch("firefighter.raid.serializers.JIRA_USER_IDS", {"special.com": "special-user-123"})
    def test_domain_specific_jira_user_with_slack_fallback(self, mock_slack_user, mock_jira_client):
        """Test domain-specific JIRA user when Slack user exists."""
        # Setup mocks
        slack_user = UserFactory(email="test@special.com")
        mock_slack_user.objects.upsert_by_email.return_value = slack_user

        domain_jira_user = JiraUser.objects.create(id="special-user-123", user=UserFactory())
        mock_jira_client.get_jira_user_from_jira_id.return_value = domain_jira_user

        with patch("firefighter.raid.serializers.User.objects.get", side_effect=User.DoesNotExist):
            reporter_user, reporter, user_domain = get_reporter_user_from_email("test@special.com")

        # Should use slack_user since reporter_user_tmp is not None
        assert reporter_user == slack_user
        assert reporter == domain_jira_user
        assert user_domain == "special.com"
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once_with("special-user-123")
