"""Tests for bidirectional synchronization between Impact, Jira and Slack."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import cache

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import (
    EnvironmentFactory,
    GroupFactory,
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models import (
    Environment,
    Incident,
    IncidentCategory,
    IncidentRole,
    IncidentRoleType,
    IncidentUpdate,
    Priority,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import JiraTicket
from firefighter.raid.sync import (
    IMPACT_TO_JIRA_STATUS_MAP,
    JIRA_TO_IMPACT_PRIORITY_MAP,
    JIRA_TO_IMPACT_STATUS_MAP,
    SyncDirection,
    handle_jira_webhook_update,
    should_skip_sync,
    sync_incident_to_jira,
    sync_jira_fields_to_incident,
    sync_jira_priority_to_incident,
    sync_jira_status_to_incident,
)


@pytest.mark.django_db
class TestSyncLoopPrevention:
    """Test sync loop prevention mechanism."""

    def test_should_skip_sync_first_call(self):
        """Test that first sync call is not skipped."""
        cache.clear()
        result = should_skip_sync("incident", "123", SyncDirection.IMPACT_TO_JIRA)
        assert result is False

    def test_should_skip_sync_second_call(self):
        """Test that immediate second sync call is skipped."""
        cache.clear()
        # First call
        should_skip_sync("incident", "456", SyncDirection.JIRA_TO_IMPACT)
        # Second call within cache timeout
        result = should_skip_sync("incident", "456", SyncDirection.JIRA_TO_IMPACT)
        assert result is True

    def test_should_skip_sync_different_direction(self):
        """Test that different sync directions are not skipped."""
        cache.clear()
        should_skip_sync("incident", "789", SyncDirection.IMPACT_TO_JIRA)
        # Different direction should not be skipped
        result = should_skip_sync("incident", "789", SyncDirection.JIRA_TO_IMPACT)
        assert result is False

    def test_should_skip_sync_different_entity(self):
        """Test that different entities are tracked separately."""
        cache.clear()
        should_skip_sync("incident", "111", SyncDirection.IMPACT_TO_JIRA)
        # Different entity should not be skipped
        result = should_skip_sync("jira_ticket", "111", SyncDirection.IMPACT_TO_JIRA)
        assert result is False


@pytest.mark.django_db
class TestJiraToImpactSync:
    """Test syncing from Jira to Impact."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()
        # Clear test-specific data only, not reference data like priorities
        JiraTicket.objects.all().delete()
        Incident.objects.all().delete()

        # Create required objects for IncidentFactory
        # Ensure we have the required related objects
        if not Environment.objects.exists():
            EnvironmentFactory()
        if not IncidentCategory.objects.exists():
            IncidentCategoryFactory()

        # Create commander role type for testing
        self.commander_role_type, _ = IncidentRoleType.objects.get_or_create(
            slug="commander",
            defaults={
                "name": "Commander",
                "description": "Incident Commander",
                "order": 1,
                "group": GroupFactory(),
            },
        )

        # Get or create a priority for IncidentFactory
        self.priority, _ = Priority.objects.get_or_create(value=3, defaults={"name": "Medium Test Priority"})
        self.incident = IncidentFactory(status=IncidentStatus.INVESTIGATING, priority=self.priority)
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-user-123", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=12345,
            key="INC-123",
            summary="Test ticket",
            description="Test description",
            reporter=self.jira_user,
            incident=self.incident,
        )

    def test_sync_jira_status_to_incident_success(self):
        """Test successful status sync from Jira to Impact."""
        result = sync_jira_status_to_incident(self.jira_ticket, "Resolved")

        assert result is True
        self.incident.refresh_from_db()
        assert self.incident.status == IncidentStatus.FIXED

    def test_sync_jira_status_to_incident_no_incident(self):
        """Test status sync when Jira ticket has no linked incident."""
        self.jira_ticket.incident = None
        self.jira_ticket.save()

        result = sync_jira_status_to_incident(self.jira_ticket, "Resolved")
        assert result is False

    def test_sync_jira_status_to_incident_unknown_status(self):
        """Test status sync with unknown Jira status."""
        result = sync_jira_status_to_incident(self.jira_ticket, "Unknown Status")
        assert result is False
        # Status should remain unchanged
        self.incident.refresh_from_db()
        assert self.incident.status == IncidentStatus.INVESTIGATING

    def test_sync_jira_status_to_incident_no_change(self):
        """Test status sync when status is already the same."""
        self.incident.status = IncidentStatus.FIXED
        self.incident.save()

        result = sync_jira_status_to_incident(self.jira_ticket, "Resolved")
        assert result is True  # Success but no actual update

    def test_sync_jira_status_to_incident_creates_update(self):
        """Test that status sync creates an IncidentUpdate record."""
        initial_count = IncidentUpdate.objects.filter(incident=self.incident).count()

        sync_jira_status_to_incident(self.jira_ticket, "Closed")

        # Check that an IncidentUpdate was created
        new_count = IncidentUpdate.objects.filter(incident=self.incident).count()
        assert new_count == initial_count + 1

        latest_update = IncidentUpdate.objects.filter(incident=self.incident).latest(
            "created_at"
        )
        assert latest_update.status == IncidentStatus.POST_MORTEM
        assert "from Jira" in latest_update.message

    def test_sync_jira_priority_to_incident_success(self):
        """Test successful priority sync from Jira to Impact."""
        priority_p2, _ = Priority.objects.get_or_create(value=2, defaults={"name": "High Priority"})

        result = sync_jira_priority_to_incident(self.jira_ticket, "High")

        assert result is True
        self.incident.refresh_from_db()
        assert self.incident.priority == priority_p2

    def test_sync_jira_priority_to_incident_unknown_priority(self):
        """Test priority sync with unknown Jira priority."""
        result = sync_jira_priority_to_incident(self.jira_ticket, "Unknown")
        assert result is False

    def test_sync_jira_fields_to_incident(self):
        """Test syncing multiple fields from Jira to Impact."""
        jira_fields = {
            "summary": "New title",
            "description": "New description",
            "assignee": {"accountId": self.jira_user.id},
        }

        result = sync_jira_fields_to_incident(self.jira_ticket, jira_fields)

        assert result is True
        self.incident.refresh_from_db()
        assert self.incident.title == "New title"
        assert self.incident.description == "New description"

        # Check that commander role was created
        commander_role = IncidentRole.objects.filter(
            incident=self.incident, role_type=self.commander_role_type
        ).first()
        assert commander_role is not None
        assert commander_role.user == self.user

    def test_handle_jira_webhook_update_status_change(self):
        """Test handling Jira webhook with status change."""
        issue_data = {"key": "INC-123", "fields": {}}
        changelog_data = {
            "items": [{"field": "status", "toString": "In Progress"}]
        }

        with patch(
            "firefighter.raid.sync.sync_jira_status_to_incident", return_value=True
        ) as mock_sync:
            result = handle_jira_webhook_update(issue_data, changelog_data)

            assert result is True
            mock_sync.assert_called_once_with(self.jira_ticket, "In Progress")

    def test_handle_jira_webhook_update_priority_change(self):
        """Test handling Jira webhook with priority change."""
        issue_data = {"key": "INC-123", "fields": {}}
        changelog_data = {"items": [{"field": "priority", "toString": "High"}]}

        with patch(
            "firefighter.raid.sync.sync_jira_priority_to_incident", return_value=True
        ) as mock_sync:
            result = handle_jira_webhook_update(issue_data, changelog_data)

            assert result is True
            mock_sync.assert_called_once_with(self.jira_ticket, "High")

    def test_handle_jira_webhook_update_no_ticket(self):
        """Test handling webhook when Jira ticket doesn't exist."""
        issue_data = {"key": "UNKNOWN-999", "fields": {}}
        changelog_data = {"items": [{"field": "status", "toString": "Resolved"}]}

        result = handle_jira_webhook_update(issue_data, changelog_data)
        assert result is False


@pytest.mark.django_db
class TestImpactToJiraSync:
    """Test syncing from Impact to Jira."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()
        # Clear test-specific data only, not reference data like priorities
        JiraTicket.objects.all().delete()
        Incident.objects.all().delete()

        # Create required objects for IncidentFactory
        # Ensure we have the required related objects
        if not Environment.objects.exists():
            EnvironmentFactory()
        if not IncidentCategory.objects.exists():
            IncidentCategoryFactory()

        # Create commander role type for testing
        self.commander_role_type, _ = IncidentRoleType.objects.get_or_create(
            slug="commander",
            defaults={
                "name": "Commander",
                "description": "Incident Commander",
                "order": 1,
                "group": GroupFactory(),
            },
        )

        # Get or create a priority for IncidentFactory
        self.priority, _ = Priority.objects.get_or_create(value=2, defaults={"name": "High Test Priority"})
        self.incident = IncidentFactory(
            title="Original title",
            description="Original description",
            status=IncidentStatus.INVESTIGATING,
            priority=self.priority,
        )
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-user-456", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=67890,
            key="INC-456",
            summary="Test ticket",
            description="Test description",
            reporter=self.jira_user,
            incident=self.incident,
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_title_change(self, mock_jira_client):
        """Test syncing title change from Impact to Jira."""
        mock_jira_client.update_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["title"])

        assert result is True
        mock_jira_client.update_issue.assert_called_once_with(
            "INC-456", {"summary": "Original title"}
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_description_change(self, mock_jira_client):
        """Test syncing description change from Impact to Jira."""
        mock_jira_client.update_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["description"])

        assert result is True
        mock_jira_client.update_issue.assert_called_once_with(
            "INC-456", {"description": "Original description"}
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_priority_change(self, mock_jira_client):
        """Test syncing priority change from Impact to Jira."""
        mock_jira_client.update_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["priority"])

        assert result is True
        mock_jira_client.update_issue.assert_called_once_with(
            "INC-456", {"priority": {"name": "High"}}
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_status_change(self, mock_jira_client):
        """Test syncing status change from Impact to Jira."""
        mock_jira_client.transition_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["status"])

        assert result is True
        mock_jira_client.transition_issue.assert_called_once_with(
            "INC-456", "In Progress"
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_commander_change(self, mock_jira_client):
        """Test syncing commander change from Impact to Jira."""
        # Create the commander role for the incident
        IncidentRole.objects.create(
            incident=self.incident,
            user=self.user,
            role_type=self.commander_role_type,
        )

        mock_jira_client.get_jira_user_from_user.return_value = self.jira_user
        mock_jira_client.update_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["commander"])

        assert result is True
        mock_jira_client.update_issue.assert_called_once_with(
            "INC-456", {"assignee": {"accountId": "jira-user-456"}}
        )

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_multiple_fields(self, mock_jira_client):
        """Test syncing multiple fields from Impact to Jira."""
        mock_jira_client.update_issue.return_value = True

        result = sync_incident_to_jira(self.incident, ["title", "description", "priority"])

        assert result is True
        expected_fields = {
            "summary": "Original title",
            "description": "Original description",
            "priority": {"name": "High"},
        }
        mock_jira_client.update_issue.assert_called_once_with("INC-456", expected_fields)

    def test_sync_incident_to_jira_no_ticket(self):
        """Test syncing when incident has no linked Jira ticket."""
        incident_without_ticket = IncidentFactory()

        result = sync_incident_to_jira(incident_without_ticket, ["title"])
        assert result is False

    @patch("firefighter.raid.sync.jira_client")
    def test_sync_incident_to_jira_with_sync_loop_prevention(self, mock_jira_client):
        """Test that sync loop prevention works."""
        # First sync should succeed
        mock_jira_client.update_issue.return_value = True
        result1 = sync_incident_to_jira(self.incident, ["title"])
        assert result1 is True

        # Second immediate sync should be skipped
        result2 = sync_incident_to_jira(self.incident, ["title"])
        assert result2 is False


@pytest.mark.django_db
class TestStatusMapping:
    """Test status mapping between systems."""

    def test_jira_to_impact_status_mapping_completeness(self):
        """Test that all common Jira statuses are mapped."""
        common_jira_statuses = [
            "Open",
            "In Progress",
            "Resolved",
            "Closed",
            "Reopened",
        ]
        for status in common_jira_statuses:
            assert status in JIRA_TO_IMPACT_STATUS_MAP

    def test_impact_to_jira_status_mapping_completeness(self):
        """Test that all Impact statuses are mapped."""
        for status in IncidentStatus:
            assert status in IMPACT_TO_JIRA_STATUS_MAP

    def test_priority_mapping_completeness(self):
        """Test that all common Jira priorities are mapped."""
        common_jira_priorities = ["Highest", "High", "Medium", "Low", "Lowest"]
        for priority in common_jira_priorities:
            assert priority in JIRA_TO_IMPACT_PRIORITY_MAP
            assert 1 <= JIRA_TO_IMPACT_PRIORITY_MAP[priority] <= 5
