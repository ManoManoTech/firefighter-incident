from __future__ import annotations

import pytest
from django.conf import settings

from firefighter.incidents.factories import UserFactory
from firefighter.incidents.models.impact import (
    Impact,
    ImpactLevel,
    ImpactType,
    LevelChoices,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import FeatureTeam, JiraTicket, JiraTicketImpact


@pytest.mark.django_db
class TestJiraTicket:
    def test_get_absolute_url(self):
        # Given
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="jira123", user=user)

        jira_ticket = JiraTicket.objects.create(
            id=12345,
            key="TEST-123",
            summary="Test ticket",
            description="Test description",
            reporter=jira_user,
        )

        # When
        result = jira_ticket.get_absolute_url()

        # Then
        expected_url = f"{settings.RAID_JIRA_API_URL}/browse/TEST-123"
        assert result == expected_url

    def test_url_property(self):
        # Given
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="jira456", user=user)

        jira_ticket = JiraTicket.objects.create(
            id=45678,
            key="TEST-456",
            summary="Test ticket 2",
            description="Test description 2",
            reporter=jira_user,
        )

        # When
        result = jira_ticket.url

        # Then
        expected_url = f"{settings.RAID_JIRA_API_URL}/browse/TEST-456"
        assert result == expected_url

    def test_url_property_equals_get_absolute_url(self):
        # Given
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="jira789", user=user)

        jira_ticket = JiraTicket.objects.create(
            id=78910,
            key="TEST-789",
            summary="Test ticket 3",
            description="Test description 3",
            reporter=jira_user,
        )

        # When & Then
        assert jira_ticket.url == jira_ticket.get_absolute_url()


@pytest.mark.django_db
class TestJiraTicketImpact:
    def test_string_representation(self):
        # Given
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="jira100", user=user)

        jira_ticket = JiraTicket.objects.create(
            id=10011,
            key="TEST-100",
            summary="Test ticket",
            description="Test description",
            reporter=jira_user,
        )

        # Create required objects for Impact
        impact_type = ImpactType.objects.create(name="Test Impact Type")
        impact_level = ImpactLevel.objects.create(
            name="High",
            impact_type=impact_type,
            value=LevelChoices.HIGH,
        )
        impact = Impact.objects.create(
            impact_type=impact_type,
            impact_level=impact_level,
            details="Test impact details",
        )

        jira_ticket_impact = JiraTicketImpact.objects.create(
            jira_ticket=jira_ticket,
            impact=impact,
        )

        # When
        result = str(jira_ticket_impact)

        # Then
        expected = f"{jira_ticket.key}: {impact}"
        assert result == expected


@pytest.mark.django_db
class TestFeatureTeam:
    def test_string_representation(self):
        # Given
        feature_team = FeatureTeam.objects.create(
            name="Test Team",
            jira_project_key="TST",
        )

        # When
        result = str(feature_team)

        # Then
        assert result == "Test Team"

    def test_get_team_property(self):
        # Given
        feature_team = FeatureTeam.objects.create(
            name="Backend Team",
            jira_project_key="BACK",
        )

        # When
        result = feature_team.get_team

        # Then
        expected = "Backend Team  BACK"
        assert result == expected

    def test_get_key_property(self):
        # Given
        feature_team = FeatureTeam.objects.create(
            name="Frontend Team",
            jira_project_key="FRONT",
        )

        # When
        result = feature_team.get_key

        # Then
        assert result == "FRONT"

    def test_unique_constraint(self):
        # Given - Create first team
        FeatureTeam.objects.create(
            name="Unique Team",
            jira_project_key="UNIQ",
        )

        # When & Then - Try to create duplicate should raise error
        with pytest.raises((Exception,)):
            FeatureTeam.objects.create(
                name="Unique Team",
                jira_project_key="UNIQ",
            )

    def test_jira_project_key_unique_constraint(self):
        # Given - Create first team
        FeatureTeam.objects.create(
            name="Team A",
            jira_project_key="SHARED",
        )

        # When & Then - Try to create another team with same key should raise error
        with pytest.raises((Exception,)):
            FeatureTeam.objects.create(
                name="Team B",
                jira_project_key="SHARED",
            )
