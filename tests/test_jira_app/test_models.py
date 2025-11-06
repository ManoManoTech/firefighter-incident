"""Tests for jira_app models."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.db.utils import IntegrityError

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.models import JiraPostMortem


@pytest.mark.django_db
class TestJiraPostMortem:
    """Test JiraPostMortem model."""

    def test_create_jira_postmortem(self):
        """Test creating a JiraPostMortem instance."""
        incident = IncidentFactory()
        user = UserFactory()

        jira_pm = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=user,
        )

        assert jira_pm.incident == incident
        assert jira_pm.jira_issue_key == "INCIDENT-123"
        assert jira_pm.jira_issue_id == "10001"
        assert jira_pm.created_by == user
        assert jira_pm.created_at is not None
        assert jira_pm.updated_at is not None

    def test_jira_postmortem_one_to_one_relationship(self):
        """Test OneToOne relationship with Incident."""
        incident = IncidentFactory()
        user = UserFactory()

        # Create first post-mortem
        jira_pm1 = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=user,
        )

        # Access from incident side
        assert hasattr(incident, "jira_postmortem_for")
        assert incident.jira_postmortem_for == jira_pm1

        # Try to create second post-mortem for same incident should fail
        with pytest.raises(IntegrityError):
            JiraPostMortem.objects.create(
                incident=incident,
                jira_issue_key="INCIDENT-456",
                jira_issue_id="10002",
                created_by=user,
            )

    def test_jira_postmortem_issue_url_property(self):
        """Test issue_url property generates correct Jira URL."""
        incident = IncidentFactory()
        user = UserFactory()

        jira_pm = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=user,
        )

        expected_url = f"{settings.RAID_JIRA_API_URL}/browse/INCIDENT-123"
        assert jira_pm.issue_url == expected_url

    @pytest.mark.django_db(transaction=True)
    def test_jira_postmortem_unique_constraints(self):
        """Test uniqueness constraints on jira_issue_key and jira_issue_id."""
        incident1 = IncidentFactory()
        incident2 = IncidentFactory()
        incident3 = IncidentFactory()
        user = UserFactory()

        # Create first post-mortem
        JiraPostMortem.objects.create(
            incident=incident1,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=user,
        )

        # Try to create second post-mortem with same jira_issue_key
        with pytest.raises(IntegrityError):
            JiraPostMortem.objects.create(
                incident=incident2,
                jira_issue_key="INCIDENT-123",  # Duplicate key
                jira_issue_id="10002",
                created_by=user,
            )

        # Try to create second post-mortem with same jira_issue_id
        with pytest.raises(IntegrityError):
            JiraPostMortem.objects.create(
                incident=incident3,
                jira_issue_key="INCIDENT-456",
                jira_issue_id="10001",  # Duplicate ID
                created_by=user,
            )

    def test_jira_postmortem_str_representation(self):
        """Test string representation of JiraPostMortem."""
        incident = IncidentFactory()
        user = UserFactory()

        jira_pm = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=user,
        )

        expected_str = f"Jira Post-mortem INCIDENT-123 for incident #{incident.id}"
        assert str(jira_pm) == expected_str

    def test_jira_postmortem_created_by_optional(self):
        """Test that created_by is optional (can be None)."""
        incident = IncidentFactory()

        jira_pm = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
            created_by=None,  # Optional field
        )

        assert jira_pm.created_by is None
        assert jira_pm.incident == incident
