"""Tests for JiraClient.get_watchers_from_jira_ticket method."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from jira.exceptions import JIRAError


@pytest.mark.django_db
class TestGetWatchersFromJiraTicket:
    """Test get_watchers_from_jira_ticket method."""

    def test_get_watchers_success_with_watchers(self, jira_client, mock_jira_api):
        """Test successful retrieval of watchers when watchers exist."""
        # Given
        mock_watchers_response = Mock()
        mock_watchers_response.raw = {
            "watchers": [
                {"accountId": "user1", "displayName": "User One"},
                {"accountId": "user2", "displayName": "User Two"},
            ]
        }
        mock_jira_api.watchers.return_value = mock_watchers_response

        # When
        result = jira_client.get_watchers_from_jira_ticket(12345)

        # Then
        mock_jira_api.watchers.assert_called_once_with(12345)
        assert len(result) == 2
        assert result[0]["accountId"] == "user1"
        assert result[1]["accountId"] == "user2"

    def test_get_watchers_success_empty_list(
        self, jira_client, mock_jira_api, caplog
    ):
        """Test successful retrieval when no watchers exist."""
        # Given
        mock_watchers_response = Mock()
        mock_watchers_response.raw = {"watchers": []}
        mock_jira_api.watchers.return_value = mock_watchers_response

        # When
        result = jira_client.get_watchers_from_jira_ticket(12345)

        # Then
        mock_jira_api.watchers.assert_called_once_with(12345)
        assert result == []
        # Should log debug message
        assert "No watchers found for jira_issue_id '12345'" in caplog.text

    def test_get_watchers_404_ticket_not_found(
        self, jira_client, mock_jira_api, caplog
    ):
        """Test handling of 404 error when ticket doesn't exist."""
        # Given
        jira_error = JIRAError(
            status_code=404,
            text="Issue does not exist or you do not have permission to see it.",
            url="https://jira.example.com/rest/api/2/issue/404295/watchers",
        )
        mock_jira_api.watchers.side_effect = jira_error

        # When
        result = jira_client.get_watchers_from_jira_ticket(404295)

        # Then
        mock_jira_api.watchers.assert_called_once_with(404295)
        assert result == []
        # Should log warning
        assert (
            "Jira ticket 404295 not found or no permission to access it"
            in caplog.text
        )

    def test_get_watchers_404_no_permission(self, jira_client, mock_jira_api, caplog):
        """Test handling of 404 error when bot has no permission."""
        # Given
        jira_error = JIRAError(
            status_code=404,
            text="Issue does not exist or you do not have permission to see it.",
            url="https://jira.example.com/rest/api/2/issue/999999/watchers",
        )
        mock_jira_api.watchers.side_effect = jira_error

        # When
        result = jira_client.get_watchers_from_jira_ticket("999999")

        # Then
        assert result == []
        assert "not found or no permission" in caplog.text

    def test_get_watchers_other_jira_error_raised(self, jira_client, mock_jira_api):
        """Test that non-404 JIRA errors are re-raised."""
        # Given
        jira_error = JIRAError(
            status_code=500, text="Internal Server Error", url="https://jira.example.com"
        )
        mock_jira_api.watchers.side_effect = jira_error

        # When / Then
        with pytest.raises(JIRAError) as exc_info:
            jira_client.get_watchers_from_jira_ticket(12345)

        assert exc_info.value.status_code == 500

    def test_get_watchers_403_error_raised(self, jira_client, mock_jira_api):
        """Test that 403 (Forbidden) errors are re-raised."""
        # Given
        jira_error = JIRAError(
            status_code=403, text="Forbidden", url="https://jira.example.com"
        )
        mock_jira_api.watchers.side_effect = jira_error

        # When / Then
        with pytest.raises(JIRAError) as exc_info:
            jira_client.get_watchers_from_jira_ticket(12345)

        assert exc_info.value.status_code == 403

    def test_get_watchers_with_string_id(self, jira_client, mock_jira_api):
        """Test get_watchers with string issue ID."""
        # Given
        mock_watchers_response = Mock()
        mock_watchers_response.raw = {"watchers": [{"accountId": "user1"}]}
        mock_jira_api.watchers.return_value = mock_watchers_response

        # When
        result = jira_client.get_watchers_from_jira_ticket("INCIDENT-123")

        # Then
        mock_jira_api.watchers.assert_called_once_with("INCIDENT-123")
        assert len(result) == 1
