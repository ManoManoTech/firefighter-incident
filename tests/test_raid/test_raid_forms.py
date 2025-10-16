from __future__ import annotations

from unittest.mock import ANY, Mock, patch

import pytest
from django.test import TestCase
from slack_sdk.errors import SlackApiError

from firefighter.incidents.factories import (
    IncidentFactory,
    PriorityFactory,
    UserFactory,
)
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.jira_app.models import JiraUser
from firefighter.raid.forms import (
    PlatformChoices,
    alert_slack_comment_ticket,
    alert_slack_new_jira_ticket,
    alert_slack_update_ticket,
    get_business_impact,
    get_internal_alert_conversations,
    get_partner_alert_conversations,
    initial_priority,
    process_jira_issue,
    send_message_to_watchers,
    set_jira_ticket_watchers_raid,
)
from firefighter.raid.models import JiraTicket
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user import SlackUser


class TestPlatformChoices(TestCase):
    """Test PlatformChoices enum."""

    def test_platform_choices_values(self):
        """Test that platform choices have correct values."""
        assert PlatformChoices.FR == "platform-FR"
        assert PlatformChoices.DE == "platform-DE"
        assert PlatformChoices.IT == "platform-IT"
        assert PlatformChoices.ES == "platform-ES"
        assert PlatformChoices.UK == "platform-UK"
        assert PlatformChoices.ALL == "platform-All"
        assert PlatformChoices.INTERNAL == "platform-Internal"


@pytest.mark.django_db
class TestInitialPriority:
    """Test initial_priority function."""

    def test_initial_priority_returns_default(self):
        """Test that initial_priority returns default priority."""
        # Given
        Priority.objects.all().delete()  # Clean slate
        default_priority = PriorityFactory(default=True, value=100)
        PriorityFactory(default=False, value=101)  # Create non-default priority

        # When
        result = initial_priority()

        # Then
        assert result == default_priority


# NOTE: Form class tests (TestCreateNormalCustomerIncidentForm,
# TestCreateRaidDocumentationRequestIncidentForm, TestCreateRaidFeatureRequestIncidentForm,
# TestCreateRaidInternalIncidentForm, TestRaidCreateIncidentSellerForm) have been removed.
#
# These forms have been replaced by the unified incident form:
# firefighter.incidents.forms.unified_incident.UnifiedIncidentForm
#
# Tests for the unified form should be added in a new file:
# tests/test_incidents/test_forms/test_unified_incident.py


@pytest.mark.django_db
class TestProcessJiraIssue:
    """Test process_jira_issue function."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-123", user=self.user)

    @patch("firefighter.raid.forms.alert_slack_new_jira_ticket")
    @patch("firefighter.raid.forms.set_jira_ticket_watchers_raid")
    @patch("firefighter.raid.forms.SelectImpactForm")
    def test_process_jira_issue(self, mock_impact_form, mock_set_watchers, mock_alert_slack):
        """Test process_jira_issue function."""
        # Given
        issue_data = {
            "id": "10001",
            "key": "TEST-123",
            "summary": "Test issue",
            "reporter": self.jira_user,
        }
        impacts_data = {"business_impact": "High"}

        mock_form_instance = Mock()
        mock_impact_form.return_value = mock_form_instance
        mock_set_watchers.return_value = None
        mock_alert_slack.return_value = None

        # When
        process_jira_issue(issue_data, self.user, self.jira_user, impacts_data)

        # Then
        # Check that JiraTicket was created
        assert JiraTicket.objects.filter(key="TEST-123").exists()

        # Check that all functions were called
        mock_impact_form.assert_called_once_with(impacts_data)
        mock_form_instance.save.assert_called_once_with(incident=ANY)
        mock_set_watchers.assert_called_once_with(ANY)
        mock_alert_slack.assert_called_once_with(ANY)


@pytest.mark.django_db
class TestSetJiraTicketWatchersRaid:
    """Test set_jira_ticket_watchers_raid function."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-123", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=10001,
            key="TEST-123",
            summary="Test ticket",
            reporter=self.jira_user,
        )

    @patch("firefighter.raid.forms.jira_client")
    def test_set_jira_ticket_watchers_success(self, mock_jira_client):
        """Test successful watcher addition."""
        # Given
        mock_default_user = Mock()
        mock_jira_client.get_jira_user_from_jira_id.return_value = mock_default_user
        mock_jira_client.jira.add_watcher.return_value = None

        # When
        set_jira_ticket_watchers_raid(self.jira_ticket)

        # Then
        mock_jira_client.jira.add_watcher.assert_called_once_with(
            issue=10001, watcher="jira-123"
        )

    @patch("firefighter.raid.forms.jira_client")
    def test_set_jira_ticket_watchers_jira_user_not_found(self, mock_jira_client):
        """Test when default JIRA user is not found."""
        # Given
        mock_jira_client.get_jira_user_from_jira_id.side_effect = JiraUserNotFoundError("Not found")

        # When
        set_jira_ticket_watchers_raid(self.jira_ticket)

        # Then
        # Should handle the exception and continue

    @patch("firefighter.raid.forms.jira_client")
    def test_set_jira_ticket_watchers_add_watcher_error(self, mock_jira_client):
        """Test when adding watcher fails."""
        # Given
        mock_default_user = Mock()
        mock_jira_client.get_jira_user_from_jira_id.return_value = mock_default_user
        mock_jira_client.jira.add_watcher.side_effect = JiraAPIError("API Error")
        mock_jira_client.jira.remove_watcher.side_effect = JiraAPIError("Remove Error")

        # When
        set_jira_ticket_watchers_raid(self.jira_ticket)

        # Then
        # Should handle both exceptions


@pytest.mark.django_db
class TestAlertSlackNewJiraTicket:
    """Test alert_slack_new_jira_ticket function."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory(email="test@example.com")
        self.slack_user = SlackUser.objects.create(
            user=self.user, slack_id="U123456"
        )
        self.jira_user = JiraUser.objects.create(id="jira-123", user=self.user)
        self.jira_ticket = JiraTicket.objects.create(
            id=10001,
            key="TEST-123",
            summary="Test ticket",
            reporter=self.jira_user,
        )

    def test_alert_slack_new_jira_ticket_with_incident_raises_error(self):
        """Test that function raises ValueError for critical incidents."""
        # Given - Create an incident and link it to the ticket
        incident = IncidentFactory()
        self.jira_ticket.incident = incident
        self.jira_ticket.save()

        # When & Then
        with pytest.raises(ValueError, match="This is a critical incident"):
            alert_slack_new_jira_ticket(self.jira_ticket)

    @patch("firefighter.raid.forms.get_partner_alert_conversations")
    @patch("firefighter.raid.forms.get_internal_alert_conversations")
    @patch("firefighter.raid.forms.SlackMessageRaidCreatedIssue")
    def test_alert_slack_new_jira_ticket_no_reporter_user(
        self, mock_message_class, mock_get_internal, mock_get_partner
    ):
        """Test when reporter user is None."""
        # Given
        mock_get_internal.return_value = Conversation.objects.none()
        mock_get_partner.return_value = Conversation.objects.none()

        # Mock message class to return proper strings instead of MagicMock
        mock_message_instance = Mock()
        mock_message_instance.get_text.return_value = "Test message"
        mock_message_instance.get_blocks.return_value = []
        mock_message_instance.get_metadata.return_value = {}
        mock_message_class.return_value = mock_message_instance

        # When
        alert_slack_new_jira_ticket(self.jira_ticket, reporter_user=None)

        # Then
        # Should log warning and return early

    @patch("firefighter.raid.forms.get_partner_alert_conversations")
    @patch("firefighter.raid.forms.get_internal_alert_conversations")
    @patch("firefighter.raid.forms.SlackMessageRaidCreatedIssue")
    def test_alert_slack_new_jira_ticket_with_slack_user(
        self, mock_message_class, mock_get_internal, mock_get_partner
    ):
        """Test with valid Slack user."""
        # Given
        mock_message = Mock()
        mock_message_class.return_value = mock_message
        mock_get_internal.return_value = Conversation.objects.none()
        mock_get_partner.return_value = Conversation.objects.none()

        # When
        with patch.object(self.slack_user, "send_private_message") as mock_send:
            alert_slack_new_jira_ticket(self.jira_ticket, reporter_user=self.user)

        # Then
        mock_send.assert_called_once_with(
            mock_message, unfurl_links=False
        )

    @patch("firefighter.raid.forms.get_partner_alert_conversations")
    @patch("firefighter.raid.forms.get_internal_alert_conversations")
    @patch("firefighter.raid.forms.SlackMessageRaidCreatedIssue")
    def test_alert_slack_new_jira_ticket_messages_disabled(
        self, mock_message_class, mock_get_internal, mock_get_partner
    ):
        """Test when user has disabled private messages."""
        # Given
        mock_message = Mock()
        mock_message_class.return_value = mock_message
        mock_get_internal.return_value = Conversation.objects.none()
        mock_get_partner.return_value = Conversation.objects.none()

        slack_error = SlackApiError("Error", response={"error": "messages_tab_disabled"})

        # When
        with patch.object(self.slack_user, "send_private_message", side_effect=slack_error):
            alert_slack_new_jira_ticket(self.jira_ticket, reporter_user=self.user)

        # Then
        # Should log warning about disabled messages


@pytest.mark.django_db
class TestAlertSlackUpdateTicket:
    """Test alert_slack_update_ticket function."""

    @patch("firefighter.raid.forms.send_message_to_watchers")
    @patch("firefighter.raid.forms.SlackMessageRaidModifiedIssue")
    def test_alert_slack_update_ticket(self, mock_message_class, mock_send_message):
        """Test alert_slack_update_ticket function."""
        # Given
        mock_message = Mock()
        mock_message_class.return_value = mock_message
        mock_send_message.return_value = True

        # When
        result = alert_slack_update_ticket(
            jira_ticket_id=10001,
            jira_ticket_key="TEST-123",
            jira_author_name="John Doe",
            jira_field_modified="Priority",
            jira_field_from="High",
            jira_field_to="Critical"
        )

        # Then
        assert result is True
        mock_message_class.assert_called_once()
        mock_send_message.assert_called_once_with(jira_issue_id=10001, message=mock_message)


@pytest.mark.django_db
class TestAlertSlackCommentTicket:
    """Test alert_slack_comment_ticket function."""

    @patch("firefighter.raid.forms.send_message_to_watchers")
    @patch("firefighter.raid.forms.SlackMessageRaidComment")
    def test_alert_slack_comment_ticket(self, mock_message_class, mock_send_message):
        """Test alert_slack_comment_ticket function."""
        # Given
        mock_message = Mock()
        mock_message_class.return_value = mock_message
        mock_send_message.return_value = True

        # When
        result = alert_slack_comment_ticket(
            webhook_event="comment_created",
            jira_ticket_id=10001,
            jira_ticket_key="TEST-123",
            author_jira_name="Jane Smith",
            comment="This is a test comment"
        )

        # Then
        assert result is True
        mock_message_class.assert_called_once()
        mock_send_message.assert_called_once_with(jira_issue_id=10001, message=mock_message)


@pytest.mark.django_db
class TestSendMessageToWatchers:
    """Test send_message_to_watchers function."""

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_no_watchers(self, mock_jira_client):
        """Test when no watchers are found."""
        # Given
        mock_jira_client.get_watchers_from_jira_ticket.return_value = None
        mock_message = Mock()

        # When
        result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_with_app_watcher(self, mock_jira_client):
        """Test when watcher is an app (should be skipped)."""
        # Given
        watchers = [
            {"accountId": "app-123", "accountType": "app"}
        ]
        mock_jira_client.get_watchers_from_jira_ticket.return_value = watchers
        mock_message = Mock()

        # When
        result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_no_account_id(self, mock_jira_client):
        """Test when watcher has no accountId."""
        # Given
        watchers = [
            {"displayName": "Test User"}  # No accountId
        ]
        mock_jira_client.get_watchers_from_jira_ticket.return_value = watchers
        mock_message = Mock()

        # When
        result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_successful(self, mock_jira_client):
        """Test successful message sending to watchers."""
        # Given
        user = UserFactory()
        slack_user = SlackUser.objects.create(user=user, slack_id="U123456")
        jira_user = JiraUser.objects.create(id="jira-watcher", user=user)

        watchers = [
            {"accountId": "jira-watcher", "accountType": "atlassian"}
        ]
        mock_jira_client.get_watchers_from_jira_ticket.return_value = watchers
        mock_jira_client.get_jira_user_from_jira_id.return_value = jira_user
        mock_message = Mock()

        # When
        with patch.object(slack_user, "send_private_message") as mock_send:
            result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True
        mock_send.assert_called_once_with(
            mock_message, unfurl_links=False
        )

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_no_slack_user(self, mock_jira_client):
        """Test when watcher has no Slack user."""
        # Given
        user = UserFactory()
        jira_user = JiraUser.objects.create(id="jira-watcher", user=user)

        watchers = [
            {"accountId": "jira-watcher", "accountType": "atlassian"}
        ]
        mock_jira_client.get_watchers_from_jira_ticket.return_value = watchers
        mock_jira_client.get_jira_user_from_jira_id.return_value = jira_user
        mock_message = Mock()

        # When
        result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True

    @patch("firefighter.raid.forms.jira_client")
    def test_send_message_to_watchers_slack_api_error(self, mock_jira_client):
        """Test when Slack API error occurs."""
        # Given
        user = UserFactory()
        slack_user = SlackUser.objects.create(user=user, slack_id="U123456")
        jira_user = JiraUser.objects.create(id="jira-watcher", user=user)

        watchers = [
            {"accountId": "jira-watcher", "accountType": "atlassian"}
        ]
        mock_jira_client.get_watchers_from_jira_ticket.return_value = watchers
        mock_jira_client.get_jira_user_from_jira_id.return_value = jira_user
        mock_message = Mock()

        # When
        with patch.object(slack_user, "send_private_message", side_effect=SlackApiError("API Error", response={})):
            result = send_message_to_watchers(10001, mock_message)

        # Then
        assert result is True


@pytest.mark.django_db
class TestGetBusinessImpact:
    """Test get_business_impact function."""

    @patch("firefighter.raid.forms.SelectImpactForm")
    def test_get_business_impact(self, mock_impact_form):
        """Test get_business_impact function."""
        # Given
        impacts_data = {"business_impact": "High"}
        mock_form_instance = Mock()
        mock_form_instance.business_impact_new = "High"
        mock_impact_form.return_value = mock_form_instance

        # When
        result = get_business_impact(impacts_data)

        # Then
        assert result == "High"
        mock_impact_form.assert_called_once_with(impacts_data)


@pytest.mark.django_db
class TestGetPartnerAlertConversations:
    """Test get_partner_alert_conversations function."""

    def test_get_partner_alert_conversations(self):
        """Test get_partner_alert_conversations function."""
        # Given
        domain = "example.com"
        conversation = Conversation.objects.create(
            channel_id="C123456",
            name="test-channel",
            tag=f"raid_alert__{domain}",
        )
        Conversation.objects.create(
            channel_id="C789012",
            name="other-channel",
            tag="other_tag",
        )

        # When
        result = get_partner_alert_conversations(domain)

        # Then
        assert conversation in result
        assert result.count() == 1


@pytest.mark.django_db
class TestGetInternalAlertConversations:
    """Test get_internal_alert_conversations function."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.jira_user = JiraUser.objects.create(id="jira-123", user=self.user)

    def test_get_internal_alert_conversations_high_impact_sbi(self):
        """Test with high business impact and SBI project."""
        # Given
        jira_ticket = JiraTicket.objects.create(
            id=10001,
            key="SBI-123",
            summary="Test ticket",
            reporter=self.jira_user,
            business_impact="High",
            project_key="SBI",
        )
        conversation = Conversation.objects.create(
            channel_id="C123456",
            name="sbi-high-channel",
            tag="raid_alert__sbi_high",
        )

        # When
        result = get_internal_alert_conversations(jira_ticket)

        # Then
        assert conversation in result

    def test_get_internal_alert_conversations_normal_impact_incidents(self):
        """Test with normal business impact and non-SBI project."""
        # Given
        jira_ticket = JiraTicket.objects.create(
            id=10002,
            key="TEST-124",
            summary="Test ticket",
            reporter=self.jira_user,
            business_impact="Medium",
            project_key="OTHER",
        )
        conversation = Conversation.objects.create(
            channel_id="C789012",
            name="incidents-normal-channel",
            tag="raid_alert__incidents_normal",
        )

        # When
        result = get_internal_alert_conversations(jira_ticket)

        # Then
        assert conversation in result
