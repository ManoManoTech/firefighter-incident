"""Tests for synchronization signal handlers."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import override_settings

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import (
    EnvironmentFactory,
    IncidentCategoryFactory,
    IncidentFactory,
    IncidentUpdateFactory,
    PriorityFactory,
    UserFactory,
)
from firefighter.incidents.models import (
    Environment,
    Incident,
    IncidentCategory,
    Priority,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import JiraTicket
from firefighter.raid.signals.incident_updated_sync import (
    sync_incident_changes_to_jira,
)


@pytest.mark.django_db
class TestIncidentSyncSignals:
    """Test incident synchronization signal handlers."""

    def setup_method(self):
        """Set up test data."""
        # Clear existing priorities to avoid conflicts
        Priority.objects.all().delete()

        # Ensure we have the required related objects
        if not Environment.objects.exists():
            EnvironmentFactory()
        if not IncidentCategory.objects.exists():
            IncidentCategoryFactory()

        self.priority = PriorityFactory(value=3)
        self.incident = IncidentFactory(
            title="Test incident",
            description="Test description",
            status=IncidentStatus.INVESTIGATING,
            priority=self.priority,
        )
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-user-789", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=11111,
            key="INC-789",
            summary="Test ticket",
            description="Test description",
            reporter=self.jira_user,
            incident=self.incident,
        )

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_changes_to_jira_on_update(self, mock_sync):
        """Test that incident changes trigger Jira sync."""
        mock_sync.return_value = True

        # Simulate an incident save with specific fields updated
        sync_incident_changes_to_jira(
            sender=Incident,
            instance=self.incident,
            created=False,
            update_fields=["title", "status"],
        )

        mock_sync.assert_called_once()
        call_args = mock_sync.call_args[0]
        assert call_args[0] == self.incident
        assert set(call_args[1]) == {"title", "status"}

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_changes_skipped_for_new_incident(self, mock_sync):
        """Test that new incidents don't trigger update sync."""
        sync_incident_changes_to_jira(
            sender=Incident,
            instance=self.incident,
            created=True,
            update_fields=["title"],
        )

        mock_sync.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_changes_skipped_for_non_sync_fields(self, mock_sync):
        """Test that non-syncable field updates are skipped."""
        sync_incident_changes_to_jira(
            sender=Incident,
            instance=self.incident,
            created=False,
            update_fields=["updated_at", "created_at"],
        )

        mock_sync.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_changes_filters_sync_fields(self, mock_sync):
        """Test that only syncable fields are passed to sync function."""
        mock_sync.return_value = True

        sync_incident_changes_to_jira(
            sender=Incident,
            instance=self.incident,
            created=False,
            update_fields=["title", "updated_at", "priority", "created_at"],
        )

        # Should only sync title and priority, not timestamp fields
        mock_sync.assert_called_once()
        call_args = mock_sync.call_args[0]
        assert call_args[0] == self.incident
        assert set(call_args[1]) == {"title", "priority"}

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=False)
    def test_sync_incident_changes_skipped_when_raid_disabled(self, mock_sync):
        """Test that sync is skipped when RAID is disabled."""
        sync_incident_changes_to_jira(
            sender=Incident,
            instance=self.incident,
            created=False,
            update_fields=["title"],
        )

        mock_sync.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_to_jira_title_change(self, mock_sync):
        """Test that IncidentUpdate with title change triggers sync."""
        mock_sync.return_value = True

        # Creating the IncidentUpdate will automatically trigger the signal
        IncidentUpdateFactory(
            incident=self.incident,
            title="New title",
            created_by=self.user,
        )

        # The signal should have been called automatically
        mock_sync.assert_called_once_with(self.incident, ["title"])

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_to_jira_status_change(self, mock_sync):
        """Test that IncidentUpdate with status change triggers sync."""
        mock_sync.return_value = True

        IncidentUpdateFactory(
            incident=self.incident,
            _status=IncidentStatus.FIXING,
            created_by=self.user,
        )

        mock_sync.assert_called_once_with(self.incident, ["status"])

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_to_jira_priority_change(self, mock_sync):
        """Test that IncidentUpdate with priority change triggers sync."""
        mock_sync.return_value = True
        new_priority, _ = Priority.objects.get_or_create(value=1, defaults={"name": "Critical Priority"})

        IncidentUpdateFactory(
            incident=self.incident,
            priority=new_priority,
            created_by=self.user,
        )

        mock_sync.assert_called_once_with(self.incident, ["priority"])

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_skipped_for_jira_origin(self, mock_sync):
        """Test that updates from Jira sync are not synced back."""
        IncidentUpdateFactory(
            incident=self.incident,
            title="New title",
            created_by=None,  # System update
            message="Title updated from Jira: New title",
        )

        mock_sync.assert_not_called()

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_multiple_fields(self, mock_sync):
        """Test that IncidentUpdate with multiple changes triggers sync."""
        mock_sync.return_value = True

        IncidentUpdateFactory(
            incident=self.incident,
            title="New title",
            description="New description",
            _status=IncidentStatus.FIXED,
            created_by=self.user,
        )

        mock_sync.assert_called_once()
        call_args = mock_sync.call_args[0]
        assert call_args[0] == self.incident
        assert set(call_args[1]) == {"title", "description", "status"}

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=True)
    def test_sync_incident_update_handles_sync_error(self, mock_sync):
        """Test that sync errors are handled gracefully."""
        mock_sync.side_effect = Exception("Sync failed")

        # Should not raise exception even if sync fails
        IncidentUpdateFactory(
            incident=self.incident,
            title="New title",
            created_by=self.user,
        )

        mock_sync.assert_called_once()

    @patch("firefighter.raid.signals.incident_updated_sync.sync_incident_to_jira")
    @override_settings(ENABLE_RAID=False)
    def test_sync_incident_update_skipped_when_raid_disabled(self, mock_sync):
        """Test that IncidentUpdate sync is skipped when RAID is disabled."""
        IncidentUpdateFactory(
            incident=self.incident,
            title="New title",
            created_by=self.user,
        )

        mock_sync.assert_not_called()
