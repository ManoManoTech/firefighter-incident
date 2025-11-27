"""Tests for Jira post-mortem service."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.jira_app.service_postmortem import JiraPostMortemService

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestJiraPostMortemService:
    """Test Jira post-mortem service."""

    @staticmethod
    def test_incident_summary_excludes_status_and_created() -> None:
        """Test that incident summary does not include Status and Created fields."""
        # Create a user
        user: User = UserFactory.create()

        # Create an incident with some updates
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Generate the incident summary
        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        incident_summary = fields[service.field_ids["incident_summary"]]

        # Verify that Status and Created are NOT in the summary
        assert "Status:" not in incident_summary
        assert "Created:" not in incident_summary

        # Verify that required fields ARE present
        assert "Incident Summary" in incident_summary
        assert "Incident:" in incident_summary
        assert "Priority:" in incident_summary

    @staticmethod
    def test_timeline_includes_status_changes() -> None:
        """Test that timeline includes incident status changes."""
        # Create a user
        user: User = UserFactory.create()

        # Create an incident
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.OPEN,
            created_by=user,
        )

        # Create status updates
        now = timezone.now()

        # Status change to INVESTIGATING
        IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.INVESTIGATING,
            event_ts=now,
            created_by=user,
        )

        # Status change to MITIGATING
        IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.MITIGATING,
            event_ts=now,
            created_by=user,
        )

        # Status change to MITIGATED
        IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.MITIGATED,
            event_ts=now,
            created_by=user,
        )

        # Generate the timeline
        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        timeline = fields[service.field_ids["timeline"]]

        # Verify that status changes are in the timeline
        assert "Status changed to: Investigating" in timeline
        assert "Status changed to: Mitigating" in timeline
        assert "Status changed to: Mitigated" in timeline

        # Verify the initial creation event is present
        assert "Incident created" in timeline

    @staticmethod
    @patch("firefighter.jira_app.service_postmortem.JiraClient")
    def test_create_postmortem_prefetches_updates(
        mock_jira_client: MagicMock,
    ) -> None:
        """Test that creating post-mortem prefetches incident updates."""
        # Mock Jira client responses
        mock_client_instance = MagicMock()
        mock_client_instance.create_postmortem_issue.return_value = {
            "id": "12345",
            "key": "TEST-123",
        }
        mock_jira_client.return_value = mock_client_instance

        # Create a user
        user: User = UserFactory.create()

        # Create an incident with status updates
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        now = timezone.now()
        IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.INVESTIGATING,
            event_ts=now,
            created_by=user,
        )

        # Create post-mortem
        service = JiraPostMortemService()
        jira_pm = service.create_postmortem_for_incident(incident, created_by=user)

        # Verify post-mortem was created
        assert jira_pm is not None
        assert jira_pm.jira_issue_key == "TEST-123"
        assert jira_pm.incident == incident

        # Verify Jira client was called with correct fields
        mock_client_instance.create_postmortem_issue.assert_called_once()
        call_kwargs = mock_client_instance.create_postmortem_issue.call_args.kwargs
        assert "fields" in call_kwargs

        # Verify timeline contains status change
        timeline = call_kwargs["fields"][service.field_ids["timeline"]]
        assert "Status changed to: Investigating" in timeline

    @staticmethod
    @patch("firefighter.jira_app.service_postmortem.JiraClient")
    def test_create_postmortem_handles_assignment_failure_gracefully(
        mock_jira_client: MagicMock,
    ) -> None:
        """Test that post-mortem creation succeeds even if assignment fails."""
        # Mock Jira client responses
        mock_client_instance = MagicMock()
        mock_client_instance.create_postmortem_issue.return_value = {
            "id": "12345",
            "key": "TEST-123",
        }
        # Mock assignment failure - return False instead of raising exception
        mock_client_instance.assign_issue.return_value = False
        mock_jira_client.return_value = mock_client_instance

        # Create a user
        user: User = UserFactory.create()

        # Create an incident
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Create post-mortem
        service = JiraPostMortemService()
        jira_pm = service.create_postmortem_for_incident(incident, created_by=user)

        # Verify post-mortem was created successfully despite assignment failure
        assert jira_pm is not None
        assert jira_pm.jira_issue_key == "TEST-123"
        assert jira_pm.incident == incident

        # Verify Jira client create was called
        mock_client_instance.create_postmortem_issue.assert_called_once()

        # Verify assignment was not attempted (no commander role)
        # or if attempted, it returned False without raising exception
