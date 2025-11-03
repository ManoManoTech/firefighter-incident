"""Tests for RAID alert notifications for P4-P5 incidents with linked Incident objects.

This module tests the alert_slack_new_jira_ticket() function behavior when called
with P4-P5 JiraTickets that have associated Incident objects (since 0.0.17 unified workflow).

Before 0.0.17: P4-P5 created only JiraTicket (no Incident) → alerts worked
Since 0.0.17: P4-P5 create Incident + JiraTicket → alerts broken due to incorrect check
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.models import JiraUser
from firefighter.raid.forms import (
    alert_slack_new_jira_ticket,
    get_internal_alert_conversations,
)
from firefighter.raid.models import JiraTicket
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user import SlackUser


@pytest.mark.django_db
class TestAlertSlackNewJiraTicketWithIncident:
    """Test alert_slack_new_jira_ticket for P4-P5 with linked Incident (unified workflow)."""

    @pytest.fixture
    def p4_priority(self):
        """Get or create P4 priority."""
        priority, _ = Priority.objects.get_or_create(value=4, defaults={"name": "P4"})
        return priority

    @pytest.fixture
    def p5_priority(self):
        """Get or create P5 priority."""
        priority, _ = Priority.objects.get_or_create(value=5, defaults={"name": "P5"})
        return priority

    @pytest.fixture
    def incident_category(self):
        """Create incident category."""
        return IncidentCategoryFactory()

    @pytest.fixture
    def reporter_user_with_slack(self):
        """Create user with Slack account."""
        user = UserFactory(email="reporter@manomano.com")
        jira_user = JiraUser.objects.create(id="jira-123", user=user)
        slack_user = SlackUser.objects.create(user=user, slack_id="U12345")
        return user, jira_user, slack_user

    @pytest.fixture
    def raid_alert_channel_sbi(self):
        """Create the raid_alert__sbi_normal channel for SBI tickets."""
        return Conversation.objects.create(
            name="incidents",
            channel_id="C_INCIDENTS",
            tag="raid_alert__sbi_normal",
        )

    def test_alert_p4_incident_with_linked_incident_should_succeed(
        self,
        p4_priority,
        incident_category,
        reporter_user_with_slack,
        raid_alert_channel_sbi,  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that P4 JiraTicket with linked Incident can send raid_alert notifications.

        This test reproduces the CURRENT BROKEN behavior since 0.0.17:
        - UnifiedIncidentForm creates Incident + JiraTicket for P4-P5
        - alert_slack_new_jira_ticket() raises ValueError because jira_ticket.incident exists
        - Notifications to #incidents channel are never sent

        Expected: Should send notifications (test will FAIL until bug is fixed)
        """
        user, jira_user, _ = reporter_user_with_slack

        # Create P4 incident (simulating UnifiedIncidentForm behavior)
        incident = IncidentFactory(
            priority=p4_priority,
            incident_category=incident_category,
            created_by=user,
        )

        # Create JiraTicket linked to Incident (UNIFIED workflow since 0.0.17)
        jira_ticket = JiraTicket.objects.create(
            id=12345,
            key="SBI-12345",
            summary="P4 incident with linked Incident",
            business_impact="N/A",
            project_key="SBI",
            reporter=jira_user,
            incident=incident,  # ← This is what breaks alert_slack_new_jira_ticket()
        )

        # Mock Slack API to capture messages sent
        with (
            patch(
                "firefighter.slack.models.user.SlackUser.send_private_message"
            ) as mock_dm,
            patch(
                "firefighter.slack.models.conversation.Conversation.send_message_and_save"
            ) as mock_channel_msg,
        ):
            # This should NOT raise ValueError and should send notifications
            alert_slack_new_jira_ticket(
                jira_ticket, reporter_user=user, reporter_email=user.email
            )

            # Verify DM was sent to reporter
            assert mock_dm.called, "Should send DM to reporter"

            # Verify message was sent to #incidents channel
            assert (
                mock_channel_msg.called
            ), "Should send message to raid_alert channel"

    def test_alert_p5_incident_with_linked_incident_should_succeed(
        self,
        p5_priority,
        incident_category,
        reporter_user_with_slack,
        raid_alert_channel_sbi,  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that P5 JiraTicket with linked Incident can send raid_alert notifications."""
        user, jira_user, _ = reporter_user_with_slack

        # Create P5 incident
        incident = IncidentFactory(
            priority=p5_priority,
            incident_category=incident_category,
            created_by=user,
        )

        # Create JiraTicket linked to Incident
        jira_ticket = JiraTicket.objects.create(
            id=12346,
            key="SBI-12346",
            summary="P5 incident with linked Incident",
            business_impact="N/A",
            project_key="SBI",
            reporter=jira_user,
            incident=incident,
        )

        # Mock Slack API
        with (
            patch(
                "firefighter.slack.models.user.SlackUser.send_private_message"
            ) as mock_dm,
            patch(
                "firefighter.slack.models.conversation.Conversation.send_message_and_save"
            ) as mock_channel_msg,
        ):
            # Should succeed for P5 as well
            alert_slack_new_jira_ticket(
                jira_ticket, reporter_user=user, reporter_email=user.email
            )

            assert mock_dm.called
            assert mock_channel_msg.called

    def test_alert_p1_incident_should_fail(
        self, incident_category, reporter_user_with_slack
    ):
        """Test that P1 JiraTicket with linked Incident correctly raises ValueError.

        P1-P3 incidents should NOT use raid_alert notifications.
        They have dedicated Slack channels and use different notification flow.
        """
        user, jira_user, _ = reporter_user_with_slack
        p1_priority, _ = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})

        incident = IncidentFactory(
            priority=p1_priority,
            incident_category=incident_category,
            created_by=user,
        )

        jira_ticket = JiraTicket.objects.create(
            id=12347,
            key="SBI-12347",
            summary="P1 critical incident",
            business_impact="High",
            project_key="SBI",
            reporter=jira_user,
            incident=incident,
        )

        # P1 should correctly raise ValueError
        with pytest.raises(
            ValueError, match="This is a critical incident, not a raid incident"
        ):
            alert_slack_new_jira_ticket(
                jira_ticket, reporter_user=user, reporter_email=user.email
            )

    def test_get_internal_alert_conversations_for_normal_impact(
        self, raid_alert_channel_sbi  # noqa: ARG002 - fixture creates channel in DB
    ):
        """Test that get_internal_alert_conversations finds raid_alert__sbi_normal channel."""
        # Create a JiraTicket with normal/N/A business impact for SBI project
        jira_user = JiraUser.objects.create(id="jira-999", user=UserFactory())
        jira_ticket = JiraTicket.objects.create(
            id=99999,
            key="SBI-99999",
            summary="Test ticket",
            business_impact="N/A",
            project_key="SBI",
            reporter=jira_user,
        )

        # Should find the raid_alert__sbi_normal channel
        channels = get_internal_alert_conversations(jira_ticket)
        channel_list = list(channels)

        assert len(channel_list) == 1
        assert channel_list[0].tag == "raid_alert__sbi_normal"
        assert channel_list[0].name == "incidents"

    def test_get_internal_alert_conversations_for_high_impact(self):
        """Test that get_internal_alert_conversations finds raid_alert__sbi_high channel."""
        # Create channel for high impact on SBI
        Conversation.objects.create(
            name="incidents-high-impact",
            channel_id="C_INCIDENTS_HIGH",
            tag="raid_alert__sbi_high",
        )

        # Create JiraTicket with High business impact for SBI
        jira_user = JiraUser.objects.create(id="jira-998", user=UserFactory())
        jira_ticket = JiraTicket.objects.create(
            id=99998,
            key="SBI-99998",
            summary="Test high impact ticket",
            business_impact="High",
            project_key="SBI",
            reporter=jira_user,
        )

        channels = get_internal_alert_conversations(jira_ticket)
        channel_list = list(channels)

        assert len(channel_list) == 1
        assert channel_list[0].tag == "raid_alert__sbi_high"
