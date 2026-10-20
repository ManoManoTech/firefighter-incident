"""Tests for raid.service module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.raid.service import get_jira_user_from_user


@pytest.mark.django_db
class TestGetJiraUserFromUser:
    """Test get_jira_user_from_user function."""

    @patch("firefighter.raid.service.jira_client")
    def test_get_jira_user_success(self, mock_jira_client, admin_user):
        """Test successful get_jira_user_from_user."""
        mock_jira_user = Mock()
        mock_jira_user.id = "test_jira_id"
        mock_jira_client.get_jira_user_from_user.return_value = mock_jira_user

        result = get_jira_user_from_user(admin_user)

        mock_jira_client.get_jira_user_from_user.assert_called_once_with(admin_user)
        assert result == mock_jira_user

    @patch("firefighter.raid.service.jira_client")
    def test_get_jira_user_fallback_to_default(self, mock_jira_client, admin_user):
        """Test fallback to default user when jira_client fails."""

        # Make the first call fail
        mock_jira_client.get_jira_user_from_user.side_effect = JiraAPIError("API error")

        # Mock the fallback call to succeed
        mock_fallback_user = Mock()
        mock_fallback_user.id = "fallback_id"
        mock_jira_client.get_jira_user_from_jira_id.return_value = mock_fallback_user

        result = get_jira_user_from_user(admin_user)

        # Should call the fallback method
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once()
        assert result == mock_fallback_user

    @patch("firefighter.raid.service.jira_client")
    @patch("firefighter.raid.service.JiraUser")
    def test_get_jira_user_fallback_to_db(self, mock_jira_user_model, mock_jira_client, admin_user):
        """Test fallback to database when both API calls fail."""

        # Make both API calls fail
        mock_jira_client.get_jira_user_from_user.side_effect = JiraAPIError("API error")
        mock_jira_client.get_jira_user_from_jira_id.side_effect = JiraUserNotFoundError("User not found")

        # Mock database fallback
        mock_db_user = Mock()
        mock_db_user.id = "db_user_id"
        mock_jira_user_model.objects.get.return_value = mock_db_user

        result = get_jira_user_from_user(admin_user)

        # Should try both API calls then fallback to DB
        mock_jira_client.get_jira_user_from_user.assert_called_once_with(admin_user)
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once()
        mock_jira_user_model.objects.get.assert_called_once()
        assert result == mock_db_user
