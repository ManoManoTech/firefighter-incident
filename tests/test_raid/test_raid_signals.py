"""Tests for RAID signal handlers."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.raid.signals.incident_updated import (
    incident_updated_close_ticket_when_mitigated_or_postmortem,
)


@pytest.mark.django_db
class TestIncidentUpdatedCloseJiraTicket:
    """Test that Jira tickets are closed when incidents reach terminal statuses."""

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_close_jira_ticket_when_status_changes_to_mitigated(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory, priority_factory
    ) -> None:
        """Test that Jira ticket is closed when incident status changes to MITIGATED for P3+."""
        user = user_factory()
        # Create P3 priority (no postmortem needed)
        p3_priority = priority_factory(value=3, name="P3", needs_postmortem=False)
        incident = incident_factory(created_by=user, priority=p3_priority)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.MITIGATED,
            created_by=user,
        )

        # Call the signal handler
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was called for P3+ incidents
        mock_close_issue.assert_called_once_with(issue_id=jira_ticket.id)

    @override_settings(ENABLE_JIRA_POSTMORTEM=True)
    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_do_not_close_jira_ticket_when_p1_mitigated(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory, priority_factory, environment_factory
    ) -> None:
        """Test that Jira ticket is NOT closed when P1 incident status changes to MITIGATED.

        For P1/P2 incidents requiring postmortem, the ticket should stay open through
        MITIGATED and POST_MORTEM phases, closing only at CLOSED.
        """
        user = user_factory()
        # Create P1 priority (needs postmortem)
        p1_priority = priority_factory(value=1, name="P1", needs_postmortem=True)
        prd_env = environment_factory(value="PRD", name="Production")
        incident = incident_factory(created_by=user, priority=p1_priority, environment=prd_env)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.MITIGATED,
            created_by=user,
        )

        # Call the signal handler
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was NOT called - P1 needs to go through postmortem first
        mock_close_issue.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_do_not_close_jira_ticket_when_status_changes_to_postmortem(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is NOT closed when incident status changes to POST_MORTEM.

        The ticket should remain open during the post-mortem phase and only close
        when the incident reaches CLOSED status.
        """
        user = user_factory()
        incident = incident_factory(created_by=user)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Call the signal handler
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was NOT called - ticket stays open during PM
        mock_close_issue.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_close_jira_ticket_when_status_changes_to_closed(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is closed when incident status changes to CLOSED (direct close)."""
        user = user_factory()
        incident = incident_factory(created_by=user)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.CLOSED,
            created_by=user,
        )

        # Call the signal handler
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was called
        mock_close_issue.assert_called_once_with(issue_id=jira_ticket.id)

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_do_not_close_jira_ticket_when_status_not_terminal(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is NOT closed for non-terminal statuses."""
        user = user_factory()
        incident = incident_factory(created_by=user)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.INVESTIGATING,
            created_by=user,
        )

        # Call the signal handler
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was NOT called
        mock_close_issue.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_do_not_close_jira_ticket_when_status_not_updated(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is NOT closed when _status is not in updated_fields."""
        user = user_factory()
        incident = incident_factory(created_by=user)
        jira_ticket = jira_ticket_factory(incident=incident)
        incident.jira_ticket = jira_ticket

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.CLOSED,
            created_by=user,
        )

        # Call the signal handler with updated_fields that don't include _status
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["priority_id"],  # Not _status
        )

        # Verify close_issue was NOT called
        mock_close_issue.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    @patch("firefighter.raid.signals.incident_updated.logger")
    def test_do_not_crash_when_jira_ticket_missing(
        self,
        mock_logger: Mock,
        mock_close_issue: Mock,
        incident_factory,
        user_factory,
    ) -> None:
        """Test that signal handler handles gracefully when Jira ticket is missing."""
        user = user_factory()
        incident = incident_factory(created_by=user)
        # No jira_ticket attached to incident

        incident_update = IncidentUpdate(
            incident=incident,
            status=IncidentStatus.CLOSED,
            created_by=user,
        )

        # Call the signal handler - should not crash
        incident_updated_close_ticket_when_mitigated_or_postmortem(
            sender="update_status",
            incident=incident,
            incident_update=incident_update,
            updated_fields=["_status"],
        )

        # Verify close_issue was NOT called
        mock_close_issue.assert_not_called()

        # Verify a warning was logged
        mock_logger.warning.assert_called_once()
