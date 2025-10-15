"""Tests for RAID signal handlers."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

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
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is closed when incident status changes to MITIGATED."""
        user = user_factory()
        incident = incident_factory(created_by=user)
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

        # Verify close_issue was called
        mock_close_issue.assert_called_once_with(issue_id=jira_ticket.id)

    @patch("firefighter.raid.signals.incident_updated.client.close_issue")
    def test_close_jira_ticket_when_status_changes_to_postmortem(
        self, mock_close_issue: Mock, incident_factory, user_factory, jira_ticket_factory
    ) -> None:
        """Test that Jira ticket is closed when incident status changes to POST_MORTEM."""
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

        # Verify close_issue was called
        mock_close_issue.assert_called_once_with(issue_id=jira_ticket.id)

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
