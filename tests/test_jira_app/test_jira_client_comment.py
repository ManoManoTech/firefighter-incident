"""Tests for JiraClient.add_comment method."""

from __future__ import annotations


def test_add_comment_posts_on_the_issue(jira_client, mock_jira_api):
    """The issue id is passed as a string, as the Jira API expects."""
    jira_client.add_comment(12345, "The incident continues on this ticket.")

    mock_jira_api.add_comment.assert_called_once_with(
        "12345", "The incident continues on this ticket."
    )
