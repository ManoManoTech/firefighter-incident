"""Tests for syncing incident key events to Jira post-mortem timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.signals import incident_key_events_updated
from firefighter.jira_app.models import JiraPostMortem

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestIncidentKeyEventsSync:
    """Test syncing incident key events to Jira post-mortem timeline."""

    @staticmethod
    @override_settings(ENABLE_JIRA_POSTMORTEM=True)
    @patch("firefighter.jira_app.signals.incident_key_events_updated.JiraClient")
    def test_key_events_update_syncs_to_jira_postmortem(
        mock_jira_client: MagicMock,
    ) -> None:
        """Test that updating key events triggers Jira post-mortem timeline update."""
        # Mock Jira client and issue
        mock_client_instance = MagicMock()
        mock_issue = MagicMock()
        mock_client_instance.jira.issue.return_value = mock_issue
        mock_jira_client.return_value = mock_client_instance

        # Create a user
        user: User = UserFactory.create()

        # Create an incident
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Create a Jira post-mortem for the incident
        JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="TEST-123",
            jira_issue_id="12345",
            created_by=user,
        )

        # Create a key event (incident update)
        now = timezone.now()
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=now,
            created_by=user,
            message="Issue was detected",
        )

        # Trigger the signal (simulating key events update)
        incident_key_events_updated.send(
            sender="test",
            incident=incident,
        )

        # Verify Jira issue was fetched
        mock_client_instance.jira.issue.assert_called_once_with("TEST-123")

        # Verify issue.update was called
        mock_issue.update.assert_called_once()
        call_kwargs = mock_issue.update.call_args.kwargs

        # Verify timeline field was updated
        assert "fields" in call_kwargs
        # Timeline field ID should be present (exact ID depends on config)
        assert len(call_kwargs["fields"]) > 0

        # Verify timeline content was generated (contains basic incident info)
        timeline_content = next(iter(call_kwargs["fields"].values()))
        assert "Timeline" in timeline_content
        assert "Incident created" in timeline_content

    @staticmethod
    @patch("firefighter.jira_app.signals.incident_key_events_updated.JiraClient")
    def test_key_events_update_no_postmortem_skips_sync(
        mock_jira_client: MagicMock,
    ) -> None:
        """Test that updating key events for incident without post-mortem skips sync."""
        # Create a user
        user: User = UserFactory.create()

        # Create an incident WITHOUT post-mortem
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.OPEN,
            created_by=user,
        )

        # Trigger the signal
        incident_key_events_updated.send(
            sender="test",
            incident=incident,
        )

        # Verify Jira client was NOT called
        mock_jira_client.assert_not_called()
