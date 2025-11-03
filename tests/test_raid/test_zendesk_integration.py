"""Comprehensive integration tests for zendesk field flow from API endpoint to Jira."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from firefighter.incidents.factories import UserFactory
from firefighter.jira_app.models import JiraUser
from firefighter.raid.client import RaidJiraClient
from firefighter.raid.models import JiraTicket
from firefighter.raid.serializers import LandbotIssueRequestSerializer


@pytest.mark.django_db
class TestZendeskFieldIntegration:
    """Integration tests for zendesk field flow from serializer to Jira API."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create a mock RaidJiraClient with mocked Jira connection."""
        with patch("firefighter.jira_app.client.JiraClient.__init__", return_value=None):
            client = RaidJiraClient()
            client.jira = Mock()
            return client

    @pytest.mark.parametrize(
        ("zendesk_value", "should_be_in_jira"),
        [
            ("ZD-12345", True),  # Valid value - should be sent to Jira
            ("", False),  # Empty string - should NOT be sent to Jira
            (None, False),  # None - should NOT be sent to Jira
            ("0", True),  # "0" is truthy in Python - should be sent
        ],
    )
    def test_zendesk_field_mapping_edge_cases(
        self, mock_jira_client, zendesk_value, should_be_in_jira
    ):
        """Test zendesk field mapping with various edge case values."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test",
                "description": "Test",
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        # Call create_issue with zendesk value
        result = mock_jira_client.create_issue(
            issuetype="Bug",
            summary="Test",
            description="Test",
            assignee=None,
            reporter="test_reporter",
            priority=1,
            zendesk_ticket_id=zendesk_value,
        )

        # Check that the Jira API was called
        assert mock_jira_client.jira.create_issue.called

        # Verify customfield_10895 presence based on expected behavior
        call_kwargs = mock_jira_client.jira.create_issue.call_args[1]

        if should_be_in_jira:
            assert "customfield_10895" in call_kwargs, (
                f"customfield_10895 should be present for zendesk_value={zendesk_value!r}"
            )
            assert call_kwargs["customfield_10895"] == str(zendesk_value)
        else:
            assert "customfield_10895" not in call_kwargs, (
                f"customfield_10895 should NOT be present for zendesk_value={zendesk_value!r}"
            )

        assert result["id"] == 12345

    @pytest.mark.parametrize(
        ("zendesk_value", "expected_param"),
        [
            ("ZD-12345", "ZD-12345"),  # Valid value
            ("", ""),  # Empty string
            (None, None),  # None
        ],
    )
    @patch("firefighter.raid.serializers.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.serializers.get_reporter_user_from_email")
    @patch("firefighter.raid.serializers.jira_client")
    def test_serializer_to_client_zendesk_flow(
        self,
        mock_jira_client,
        mock_get_reporter,
        mock_alert_slack,
        zendesk_value,
        expected_param,
    ):
        """Test that serializer correctly passes zendesk value to jira_client."""
        # Setup mocks
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-123", user=user)
        mock_get_reporter.return_value = (user, jira_user, "manomano.com")
        mock_alert_slack.return_value = None

        mock_jira_client.create_issue.return_value = {
            "id": "12345",
            "key": "TEST-123",
            "summary": "Test",
            "reporter": jira_user,
        }

        # Create serializer and validated_data
        serializer = LandbotIssueRequestSerializer()
        validated_data = {
            "reporter_email": "test@manomano.com",
            "issue_type": "Incident",
            "summary": "Test",
            "description": "Test",
            "labels": [],
            "priority": 1,
            "seller_contract_id": None,
            "zoho": None,
            "zendesk": zendesk_value,
            "platform": "FR",
            "incident_category": None,
            "business_impact": None,
            "environments": ["PRD"],
            "suggested_team_routing": "TEAM1",
            "project": "SBI",
            "attachments": None,
        }

        # Call create
        result = serializer.create(validated_data)

        # Verify jira_client.create_issue was called
        assert mock_jira_client.create_issue.called

        # Check zendesk_ticket_id parameter
        create_call = mock_jira_client.create_issue.call_args[1]
        assert "zendesk_ticket_id" in create_call
        assert create_call["zendesk_ticket_id"] == expected_param

        assert isinstance(result, JiraTicket)
        mock_alert_slack.assert_called_once()

    @patch("firefighter.raid.serializers.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.serializers.get_reporter_user_from_email")
    @patch("firefighter.raid.serializers.jira_client")
    def test_serializer_without_zendesk_field(
        self, mock_jira_client, mock_get_reporter, mock_alert_slack
    ):
        """Test that serializer works when zendesk field is not provided."""
        # Setup mocks
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="test-456", user=user)
        mock_get_reporter.return_value = (user, jira_user, "manomano.com")
        mock_alert_slack.return_value = None

        mock_jira_client.create_issue.return_value = {
            "id": "12346",
            "key": "TEST-124",
            "summary": "Test",
            "reporter": jira_user,
        }

        serializer = LandbotIssueRequestSerializer()
        validated_data = {
            "reporter_email": "test@manomano.com",
            "issue_type": "Incident",
            "summary": "Test without zendesk",
            "description": "Test",
            "labels": [],
            "priority": 1,
            "seller_contract_id": None,
            "zoho": None,
            # zendesk field NOT provided
            "platform": "FR",
            "incident_category": None,
            "business_impact": None,
            "environments": ["PRD"],
            "suggested_team_routing": "TEAM1",
            "project": "SBI",
            "attachments": None,
        }

        result = serializer.create(validated_data)

        # Verify zendesk_ticket_id parameter is None
        create_call = mock_jira_client.create_issue.call_args[1]
        assert "zendesk_ticket_id" in create_call
        assert create_call["zendesk_ticket_id"] is None

        assert isinstance(result, JiraTicket)
