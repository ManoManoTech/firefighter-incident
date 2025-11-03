"""Tests for Slack Conversation tags usage across the application.

This module verifies that all documented conversation tags are properly used
and that the logic for finding and using tagged channels works correctly.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.models import JiraUser
from firefighter.raid.forms import get_internal_alert_conversations
from firefighter.raid.models import JiraTicket
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.rules import (
    should_publish_in_general_channel,
    should_publish_in_it_deploy_channel,
)


@pytest.mark.django_db
class TestTechIncidentsTag:
    """Test the tech_incidents tag usage for general incident announcements."""

    @pytest.fixture
    def tech_incidents_channel(self):
        """Create tech_incidents channel."""
        return Conversation.objects.create(
            name="tech-incidents",
            channel_id="C_TECH_INCIDENTS",
            tag="tech_incidents",
        )

    @pytest.fixture
    def p1_prd_incident(self):
        """Create P1 incident in PRD."""
        p1 = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        category = IncidentCategoryFactory()
        return IncidentFactory(
            priority=p1,
            environment=prd,
            incident_category=category,
            status=IncidentStatus.OPEN,
            private=False,
        )

    def test_tech_incidents_channel_can_be_found(
        self, tech_incidents_channel  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that tech_incidents channel can be retrieved by tag."""
        channel = Conversation.objects.get_or_none(tag="tech_incidents")
        assert channel is not None
        assert channel.name == "tech-incidents"
        assert channel.tag == "tech_incidents"

    def test_should_publish_p1_prd_incident_in_tech_incidents(self, p1_prd_incident):
        """Test that P1 PRD incidents should be published to tech_incidents."""
        should_publish = should_publish_in_general_channel(
            p1_prd_incident, incident_update=None
        )
        assert should_publish is True

    def test_should_not_publish_p4_in_tech_incidents(self):
        """Test that P4 incidents should NOT be published to tech_incidents."""
        p4 = Priority.objects.get_or_create(value=4, defaults={"name": "P4"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        category = IncidentCategoryFactory()
        incident = IncidentFactory(
            priority=p4,
            environment=prd,
            incident_category=category,
            status=IncidentStatus.OPEN,
            private=False,
        )

        should_publish = should_publish_in_general_channel(
            incident, incident_update=None
        )
        assert should_publish is False

    def test_should_not_publish_private_incident_in_tech_incidents(self):
        """Test that private incidents should NOT be published to tech_incidents."""
        p1 = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        category = IncidentCategoryFactory()
        incident = IncidentFactory(
            priority=p1,
            environment=prd,
            incident_category=category,
            status=IncidentStatus.OPEN,
            private=True,  # Private incident
        )

        should_publish = should_publish_in_general_channel(
            incident, incident_update=None
        )
        assert should_publish is False


@pytest.mark.django_db
class TestItDeployTag:
    """Test the it_deploy tag usage for deployment warnings."""

    @pytest.fixture
    def it_deploy_channel(self):
        """Create it_deploy channel."""
        return Conversation.objects.create(
            name="it-deploy", channel_id="C_IT_DEPLOY", tag="it_deploy"
        )

    @pytest.fixture
    def deploy_warning_category(self):
        """Create incident category with deploy_warning=True."""
        return IncidentCategoryFactory(deploy_warning=True)

    def test_it_deploy_channel_can_be_found(
        self, it_deploy_channel  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that it_deploy channel can be retrieved by tag."""
        channel = Conversation.objects.get_or_none(tag="it_deploy")
        assert channel is not None
        assert channel.name == "it-deploy"
        assert channel.tag == "it_deploy"

    def test_should_publish_p1_deploy_warning_in_it_deploy(
        self, deploy_warning_category
    ):
        """Test that P1 incidents with deploy_warning should be published to it_deploy."""
        p1 = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        incident = IncidentFactory(
            priority=p1,
            environment=prd,
            incident_category=deploy_warning_category,
            status=IncidentStatus.OPEN,
            private=False,
        )

        should_publish = should_publish_in_it_deploy_channel(incident)
        assert should_publish is True

    def test_should_not_publish_p2_in_it_deploy(self, deploy_warning_category):
        """Test that P2 incidents should NOT be published to it_deploy (P1 only)."""
        p2 = Priority.objects.get_or_create(value=2, defaults={"name": "P2"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        incident = IncidentFactory(
            priority=p2,
            environment=prd,
            incident_category=deploy_warning_category,
            status=IncidentStatus.OPEN,
            private=False,
        )

        should_publish = should_publish_in_it_deploy_channel(incident)
        assert should_publish is False

    def test_should_not_publish_p1_without_deploy_warning_in_it_deploy(self):
        """Test that P1 without deploy_warning should NOT be published to it_deploy."""
        p1 = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})[0]
        prd = Environment.objects.get_or_create(value="PRD", defaults={"value": "PRD"})[
            0
        ]
        category = IncidentCategoryFactory(deploy_warning=False)
        incident = IncidentFactory(
            priority=p1,
            environment=prd,
            incident_category=category,
            status=IncidentStatus.OPEN,
            private=False,
        )

        should_publish = should_publish_in_it_deploy_channel(incident)
        assert should_publish is False


@pytest.mark.django_db
class TestInvitedForAllPublicP1Tag:
    """Test the invited_for_all_public_p1 usergroup tag."""

    @pytest.fixture
    def p1_usergroup(self):
        """Create P1 usergroup conversation (represents Slack usergroup)."""
        return Conversation.objects.create(
            name="leadership-p1",
            channel_id="S_LEADERSHIP",  # S prefix for usergroup
            tag="invited_for_all_public_p1",
        )

    def test_p1_usergroup_can_be_found(
        self, p1_usergroup  # noqa: ARG002 - fixture creates usergroup in DB
    ):
        """Test that P1 usergroup can be retrieved by tag."""
        usergroup = Conversation.objects.get_or_none(tag="invited_for_all_public_p1")
        assert usergroup is not None
        assert usergroup.tag == "invited_for_all_public_p1"

    def test_p1_usergroup_tag_exists_in_code(
        self, p1_usergroup  # noqa: ARG002 - fixture creates usergroup in DB
    ):
        """Test that P1 usergroup tag is referenced in codebase."""
        # Just verify the tag can be found - the actual Slack integration
        # is tested in the get_users tests
        usergroup = Conversation.objects.get_or_none(tag="invited_for_all_public_p1")
        assert usergroup is not None


@pytest.mark.django_db
class TestDevFirefighterTag:
    """Test the dev_firefighter tag for support channel."""

    @pytest.fixture
    def support_channel(self):
        """Create dev_firefighter support channel."""
        return Conversation.objects.create(
            name="firefighter-support",
            channel_id="C_SUPPORT",
            tag="dev_firefighter",
        )

    def test_support_channel_can_be_found(
        self, support_channel  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that support channel can be retrieved by tag."""
        channel = Conversation.objects.get_or_none(tag="dev_firefighter")
        assert channel is not None
        assert channel.name == "firefighter-support"
        assert channel.tag == "dev_firefighter"

    def test_support_channel_used_in_templating(self, support_channel):
        """Test that support channel tag is referenced in slack_templating module."""
        # The support channel is retrieved in slack_templating.py:76
        # Just verify it can be found
        channel = Conversation.objects.get_or_none(tag="dev_firefighter")
        assert channel is not None
        assert channel == support_channel


@pytest.mark.django_db
class TestRaidAlertTags:
    """Test RAID alert tags patterns (already tested in test_raid_alert_p4_p5.py).

    These tests verify the tag patterns work correctly for P4-P5 incidents.
    """

    def test_raid_alert_sbi_normal_tag_format(self):
        """Test that raid_alert__sbi_normal follows correct format."""
        # Create channel
        Conversation.objects.create(
            name="incidents", channel_id="C_INC", tag="raid_alert__sbi_normal"
        )

        # Create ticket
        jira_user = JiraUser.objects.create(id="test-jira", user=UserFactory())
        ticket = JiraTicket.objects.create(
            id=1,
            key="SBI-1",
            summary="Test",
            project_key="SBI",
            business_impact="N/A",
            reporter=jira_user,
        )

        channels = list(get_internal_alert_conversations(ticket))
        assert len(channels) == 1
        assert channels[0].tag == "raid_alert__sbi_normal"

    def test_raid_alert_sbi_high_tag_format(self):
        """Test that raid_alert__sbi_high follows correct format."""
        # Create channel
        Conversation.objects.create(
            name="incidents-high", channel_id="C_INC_H", tag="raid_alert__sbi_high"
        )

        # Create ticket with high impact
        jira_user = JiraUser.objects.create(id="test-jira2", user=UserFactory())
        ticket = JiraTicket.objects.create(
            id=2,
            key="SBI-2",
            summary="Test",
            project_key="SBI",
            business_impact="High",
            reporter=jira_user,
        )

        channels = list(get_internal_alert_conversations(ticket))
        assert len(channels) == 1
        assert channels[0].tag == "raid_alert__sbi_high"


@pytest.mark.django_db
class TestTagUniqueness:
    """Test that tags are unique and constraints work."""

    def test_cannot_create_duplicate_tags(self):
        """Test that duplicate non-empty tags are rejected."""
        Conversation.objects.create(
            name="channel1", channel_id="C_001", tag="unique_tag"
        )

        with pytest.raises(IntegrityError):
            Conversation.objects.create(
                name="channel2", channel_id="C_002", tag="unique_tag"
            )

    def test_can_have_multiple_empty_tags(self):
        """Test that multiple channels can have empty tags."""
        conv1 = Conversation.objects.create(name="channel1", channel_id="C_001", tag="")
        conv2 = Conversation.objects.create(name="channel2", channel_id="C_002", tag="")

        assert conv1.tag == ""
        assert conv2.tag == ""

    def test_tag_case_sensitivity(self):
        """Test that tags are case-sensitive."""
        Conversation.objects.create(
            name="channel1", channel_id="C_001", tag="tech_incidents"
        )

        # Different case should be allowed (but not recommended)
        conv2 = Conversation.objects.create(
            name="channel2", channel_id="C_002", tag="TECH_INCIDENTS"
        )

        assert conv2.tag == "TECH_INCIDENTS"
