"""Tests for Jira post-mortem issue link creation with robust error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jira import exceptions as jira_exceptions

from firefighter.jira_app.client import JiraClient


class TestPostmortemIssueLink:
    """Test robust issue link creation between incident and post-mortem."""

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_issue_link_success_first_try(mock_jira_class: MagicMock) -> None:
        """Test that issue link is created successfully on first try with 'Relates' type."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue validation - both issues exist
        mock_parent_issue = MagicMock()
        mock_postmortem_issue = MagicMock()
        mock_jira_instance.issue.side_effect = [
            mock_parent_issue,
            mock_postmortem_issue,
        ]

        # Mock successful link creation
        mock_jira_instance.create_issue_link.return_value = None

        # Create client and call the method
        client = JiraClient()
        client._create_issue_link_safe(
            parent_issue_key="INCIDENT-123", postmortem_issue_key="PM-456"
        )

        # Verify link was created with 'Relates' type
        mock_jira_instance.create_issue_link.assert_called_once_with(
            type="Relates",
            inwardIssue="INCIDENT-123",
            outwardIssue="PM-456",
            comment={"body": "Post-mortem PM-456 created for incident INCIDENT-123"},
        )

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_issue_link_fallback_to_blocks(mock_jira_class: MagicMock) -> None:
        """Test that issue link falls back to 'Blocks' type when 'Relates' fails."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue validation - both issues exist (called multiple times)
        mock_issue = MagicMock()
        mock_jira_instance.issue.return_value = mock_issue

        # Mock link creation: first attempt fails, second succeeds
        mock_jira_instance.create_issue_link.side_effect = [
            jira_exceptions.JIRAError(
                status_code=400, text="Link type 'Relates' not found"
            ),
            None,  # Second attempt succeeds
        ]

        # Create client and call the method
        client = JiraClient()
        client._create_issue_link_safe(
            parent_issue_key="INCIDENT-123", postmortem_issue_key="PM-456"
        )

        # Verify it tried 'Relates' first, then 'Blocks'
        assert mock_jira_instance.create_issue_link.call_count == 2
        first_call = mock_jira_instance.create_issue_link.call_args_list[0]
        second_call = mock_jira_instance.create_issue_link.call_args_list[1]
        assert first_call.kwargs["type"] == "Relates"
        assert second_call.kwargs["type"] == "Blocks"

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_issue_link_all_types_fail(mock_jira_class: MagicMock) -> None:
        """Test that method handles gracefully when all link types fail."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue validation - both issues exist
        mock_issue = MagicMock()
        mock_jira_instance.issue.return_value = mock_issue

        # Mock link creation: all attempts fail
        mock_jira_instance.create_issue_link.side_effect = jira_exceptions.JIRAError(
            status_code=400, text="Link type not found"
        )

        # Create client and call the method - should not raise exception
        client = JiraClient()
        client._create_issue_link_safe(
            parent_issue_key="INCIDENT-123", postmortem_issue_key="PM-456"
        )

        # Verify it tried all 3 link types
        assert mock_jira_instance.create_issue_link.call_count == 3

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_issue_link_parent_not_found(mock_jira_class: MagicMock) -> None:
        """Test that method handles gracefully when parent issue doesn't exist."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue validation: parent issue not found
        mock_jira_instance.issue.side_effect = jira_exceptions.JIRAError(
            status_code=404, text="Issue not found"
        )

        # Create client and call the method - should not raise exception
        client = JiraClient()
        client._create_issue_link_safe(
            parent_issue_key="INCIDENT-999", postmortem_issue_key="PM-456"
        )

        # Verify link creation was not attempted
        mock_jira_instance.create_issue_link.assert_not_called()

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_postmortem_issue_with_link(mock_jira_class: MagicMock) -> None:
        """Test that post-mortem issue is created and linked successfully."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue creation
        mock_created_issue = MagicMock()
        mock_created_issue.key = "PM-789"
        mock_created_issue.id = "12345"
        mock_jira_instance.create_issue.return_value = mock_created_issue

        # Mock issue validation
        mock_issue = MagicMock()
        mock_jira_instance.issue.return_value = mock_issue

        # Mock link creation
        mock_jira_instance.create_issue_link.return_value = None

        # Create client and call the method
        client = JiraClient()
        result = client.create_postmortem_issue(
            project_key="PM",
            issue_type="Post-mortem",
            fields={"summary": "Test post-mortem"},
            parent_issue_key="INCIDENT-123",
        )

        # Verify issue was created
        mock_jira_instance.create_issue.assert_called_once()
        assert result == {"key": "PM-789", "id": "12345"}

        # Verify link was created
        mock_jira_instance.create_issue_link.assert_called_once()

    @staticmethod
    @patch("firefighter.jira_app.client.JIRA")
    def test_create_postmortem_issue_link_fails_but_issue_created(
        mock_jira_class: MagicMock,
    ) -> None:
        """Test that post-mortem issue is still created even if linking fails."""
        # Setup mock
        mock_jira_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_instance

        # Mock issue creation
        mock_created_issue = MagicMock()
        mock_created_issue.key = "PM-789"
        mock_created_issue.id = "12345"
        mock_jira_instance.create_issue.return_value = mock_created_issue

        # Mock issue validation - parent doesn't exist
        mock_jira_instance.issue.side_effect = jira_exceptions.JIRAError(
            status_code=404, text="Issue not found"
        )

        # Create client and call the method
        client = JiraClient()
        result = client.create_postmortem_issue(
            project_key="PM",
            issue_type="Post-mortem",
            fields={"summary": "Test post-mortem"},
            parent_issue_key="INCIDENT-999",
        )

        # Verify issue was created successfully despite link failure
        mock_jira_instance.create_issue.assert_called_once()
        assert result == {"key": "PM-789", "id": "12345"}

        # Verify link creation was attempted but failed gracefully
        mock_jira_instance.create_issue_link.assert_not_called()
