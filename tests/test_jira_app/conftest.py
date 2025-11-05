"""Fixtures for jira_app tests."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from firefighter.jira_app.client import JiraClient


@pytest.fixture
def mock_jira_api():
    """Create a mock JIRA API object."""
    return Mock()


@pytest.fixture
def jira_client(mock_jira_api):
    """Create a JiraClient with mocked JIRA API."""
    with patch("firefighter.jira_app.client.JIRA", return_value=mock_jira_api):
        client = JiraClient()
        client.jira = mock_jira_api
        return client
