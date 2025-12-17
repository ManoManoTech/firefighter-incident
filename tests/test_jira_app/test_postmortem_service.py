"""Tests for Jira post-mortem service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.jira_app.client import JiraUser
from firefighter.jira_app.models import JiraUser as JiraUserDB
from firefighter.jira_app.service_postmortem import JiraPostMortemService
from firefighter.raid.models import JiraTicket

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
    def test_generate_issue_fields_sets_due_date() -> None:
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.OPEN,
            created_by=user,
        )
        incident.created_at = datetime(2024, 1, 1, tzinfo=UTC)
        incident.save(update_fields=["created_at"])

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        expected_due = (
            service._add_business_days(incident.created_at, 40).date().isoformat()
        )
        assert fields["duedate"] == expected_due

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

    @staticmethod
    @pytest.mark.django_db
    def test_assigns_commander_without_jira_user() -> None:
        """Commander without Jira user should trigger lookup and assignment."""
        service = JiraPostMortemService()
        mock_client = MagicMock()
        mock_client.create_postmortem_issue.return_value = {"id": "1", "key": "INC-1"}
        mock_client.assign_issue.return_value = True
        mock_client.get_jira_user_from_user.return_value = JiraUser(
            id="acct-123", user=None
        )
        service.client = mock_client

        user = UserFactory()
        incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )
        role_type, _ = IncidentRoleType.objects.get_or_create(
            slug="commander",
            defaults={
                "name": "Commander",
                "summary": "cmd",
                "description": "Commander role",
            },
        )
        IncidentRole.objects.create(incident=incident, user=user, role_type=role_type)

        service.create_postmortem_for_incident(incident, created_by=user)

        mock_client.get_jira_user_from_user.assert_called_once_with(user)
        mock_client.assign_issue.assert_called_once_with(
            issue_key="INC-1", account_id="acct-123"
        )

    @staticmethod
    def test_replicate_custom_fields_all_present() -> None:
        """Test that all custom fields are replicated when present."""
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
            custom_fields={
                "zendesk_ticket_id": "12345",
                "zoho_desk_ticket_id": "67890",
                "seller_contract_id": "98765",
                "platforms": ["platform-FR"],
                "environments": ["PRD", "STG"],
            },
        )

        # Create a Jira user for reporter
        jira_user = JiraUserDB.objects.create(
            id="test-jira-user-id",
            user=user,
        )

        # Create a Jira ticket with business_impact
        JiraTicket.objects.create(
            id=12345,
            incident=incident,
            key="TEST-123",
            reporter=jira_user,
            business_impact="High",
        )
        incident.refresh_from_db()

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        # Verify Priority is replicated
        assert "customfield_11064" in fields
        assert fields["customfield_11064"] == {"value": str(incident.priority.value)}

        # Verify Environments are replicated
        assert "customfield_11049" in fields
        assert fields["customfield_11049"] == [{"value": "PRD"}, {"value": "STG"}]

        # Verify Zendesk ticket is replicated
        assert "customfield_10895" in fields
        assert fields["customfield_10895"] == "12345"

        # Verify Zoho desk ticket is replicated
        assert "customfield_10896" in fields
        assert fields["customfield_10896"] == "67890"

        # Verify Seller Contract ID is replicated
        assert "customfield_10908" in fields
        assert fields["customfield_10908"] == "98765"

        # Verify Platform is replicated (without "platform-" prefix)
        assert "customfield_10201" in fields
        assert fields["customfield_10201"] == {"value": "FR"}

        # Verify Business Impact is replicated
        assert "customfield_10936" in fields
        assert fields["customfield_10936"] == {"value": "High"}

    @staticmethod
    def test_replicate_custom_fields_empty_not_sent() -> None:
        """Test that empty custom fields are not sent to Jira."""
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
            custom_fields={},  # No custom fields
        )

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        # Priority should always be present
        assert "customfield_11064" in fields

        # Other fields should not be present when empty
        assert "customfield_11049" not in fields  # Environments
        assert "customfield_10895" not in fields  # Zendesk
        assert "customfield_10896" not in fields  # Zoho
        assert "customfield_10908" not in fields  # Seller
        assert "customfield_10201" not in fields  # Platform
        assert "customfield_10936" not in fields  # Business Impact (no jira_ticket)

    @staticmethod
    def test_replicate_custom_fields_partial() -> None:
        """Test that only present custom fields are replicated."""
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
            custom_fields={
                "zendesk_ticket_id": "12345",
                "environments": ["PRD"],
                # seller_contract_id and zoho_desk_ticket_id are missing
            },
        )

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        # Present fields should be replicated
        assert "customfield_10895" in fields  # Zendesk
        assert fields["customfield_10895"] == "12345"
        assert "customfield_11049" in fields  # Environments
        assert fields["customfield_11049"] == [{"value": "PRD"}]

        # Missing fields should not be present
        assert "customfield_10896" not in fields  # Zoho
        assert "customfield_10908" not in fields  # Seller
        assert "customfield_10201" not in fields  # Platform

    @staticmethod
    def test_business_impact_not_replicated_when_na() -> None:
        """Test that business_impact is not replicated when it's 'N/A' or empty."""
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Create a Jira user for reporter
        jira_user = JiraUserDB.objects.create(
            id="test-jira-user-id-2",
            user=user,
        )

        # Create a Jira ticket with business_impact = "N/A"
        JiraTicket.objects.create(
            id=12346,
            incident=incident,
            key="TEST-123",
            reporter=jira_user,
            business_impact="N/A",
        )
        incident.refresh_from_db()

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        # Business Impact should not be present when "N/A"
        assert "customfield_10936" not in fields

    @staticmethod
    def test_platform_prefix_removal() -> None:
        """Test that 'platform-' prefix is removed from platform value."""
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
            custom_fields={
                "platforms": ["platform-DE"],
            },
        )

        service = JiraPostMortemService()
        fields = service._generate_issue_fields(incident)

        # Verify platform prefix is removed
        assert "customfield_10201" in fields
        assert fields["customfield_10201"] == {"value": "DE"}
