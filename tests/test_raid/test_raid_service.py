"""Tests for raid.service module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.raid.service import (
    CustomerIssueData,
    check_issue_id,
    create_issue_customer,
    create_issue_documentation_request,
    create_issue_feature_request,
    create_issue_internal,
    create_issue_seller,
    get_jira_user_from_user,
)


class TestCustomerIssueData:
    """Test the CustomerIssueData dataclass."""

    def test_customer_issue_data_creation(self):
        """Test creating CustomerIssueData with all fields."""
        data = CustomerIssueData(
            priority=1,
            labels=["urgent", "customer"],
            platform="web",
            business_impact="high",
            team_to_be_routed="backend-team",
            area="payments",
            zendesk_ticket_id="12345",
            incident_category="payment-issue",
        )

        assert data.priority == 1
        assert data.labels == ["urgent", "customer"]
        assert data.platform == "web"
        assert data.business_impact == "high"
        assert data.team_to_be_routed == "backend-team"
        assert data.area == "payments"
        assert data.zendesk_ticket_id == "12345"
        assert data.incident_category == "payment-issue"

    def test_customer_issue_data_defaults(self):
        """Test CustomerIssueData with default values."""
        data = CustomerIssueData(
            priority=None,
            labels=None,
            platform="mobile",
            business_impact=None,
            team_to_be_routed=None,
            area=None,
            zendesk_ticket_id=None,
        )

        assert data.priority is None
        assert data.labels is None
        assert data.platform == "mobile"
        assert data.business_impact is None
        assert data.team_to_be_routed is None
        assert data.area is None
        assert data.zendesk_ticket_id is None
        assert data.incident_category is None  # Default value


@pytest.mark.django_db
class TestGetJiraUserFromUser:
    """Test get_jira_user_from_user function."""

    @patch("firefighter.raid.service.jira_client")
    def test_get_jira_user_success(self, mock_jira_client, admin_user):
        """Test successful get_jira_user_from_user."""
        mock_jira_user = Mock()
        mock_jira_user.id = "test_jira_id"
        mock_jira_client.get_jira_user_from_user.return_value = mock_jira_user

        result = get_jira_user_from_user(admin_user)

        mock_jira_client.get_jira_user_from_user.assert_called_once_with(admin_user)
        assert result == mock_jira_user

    @patch("firefighter.raid.service.jira_client")
    def test_get_jira_user_fallback_to_default(self, mock_jira_client, admin_user):
        """Test fallback to default user when jira_client fails."""

        # Make the first call fail
        mock_jira_client.get_jira_user_from_user.side_effect = JiraAPIError("API error")

        # Mock the fallback call to succeed
        mock_fallback_user = Mock()
        mock_fallback_user.id = "fallback_id"
        mock_jira_client.get_jira_user_from_jira_id.return_value = mock_fallback_user

        result = get_jira_user_from_user(admin_user)

        # Should call the fallback method
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once()
        assert result == mock_fallback_user

    @patch("firefighter.raid.service.jira_client")
    @patch("firefighter.raid.service.JiraUser")
    def test_get_jira_user_fallback_to_db(self, mock_jira_user_model, mock_jira_client, admin_user):
        """Test fallback to database when both API calls fail."""

        # Make both API calls fail
        mock_jira_client.get_jira_user_from_user.side_effect = JiraAPIError("API error")
        mock_jira_client.get_jira_user_from_jira_id.side_effect = JiraUserNotFoundError("User not found")

        # Mock database fallback
        mock_db_user = Mock()
        mock_db_user.id = "db_user_id"
        mock_jira_user_model.objects.get.return_value = mock_db_user

        result = get_jira_user_from_user(admin_user)

        # Should try both API calls then fallback to DB
        mock_jira_client.get_jira_user_from_user.assert_called_once_with(admin_user)
        mock_jira_client.get_jira_user_from_jira_id.assert_called_once()
        mock_jira_user_model.objects.get.assert_called_once()
        assert result == mock_db_user


class TestCheckIssueId:
    """Test check_issue_id function."""

    def test_check_issue_id_with_valid_issue(self):
        """Test check_issue_id with valid issue object."""
        mock_issue = {"id": "TICKET-123"}

        result = check_issue_id(mock_issue, "Test Title", "test_reporter")
        assert result == "TICKET-123"

    def test_check_issue_id_with_none_issue(self):
        """Test check_issue_id with None issue should raise AttributeError."""
        # The actual code doesn't check for None, so it raises AttributeError
        with pytest.raises(AttributeError):
            check_issue_id(None, "Test Title", "test_reporter")

    def test_check_issue_id_with_issue_without_id(self):
        """Test check_issue_id with issue object without id."""
        mock_issue = {"id": None}

        with pytest.raises(JiraAPIError):
            check_issue_id(mock_issue, "Test Title", "test_reporter")


@pytest.mark.django_db
class TestCreateIssueFunctions:
    """Test the create_issue_* functions."""

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_customer(self, mock_jira_client):
        """Test create_issue_customer function."""
        # Setup mock
        mock_issue = Mock()
        mock_issue.id = "CUST-123"
        mock_jira_client.create_issue.return_value = mock_issue

        # Create test data
        issue_data = CustomerIssueData(
            priority=1,
            labels=["customer"],
            platform="web",
            business_impact="high",
            team_to_be_routed="support-team",
            area="billing",
            zendesk_ticket_id="ZD-456",
            incident_category="billing-issue",
        )

        # Call function
        result = create_issue_customer(
            title="Customer Issue",
            description="Customer is experiencing billing problems",
            reporter="reporter_id",
            issue_data=issue_data,
        )

        # Verify jira_client.create_issue was called with correct parameters
        mock_jira_client.create_issue.assert_called_once_with(
            issuetype="Incident",
            summary="Customer Issue",
            description="Customer is experiencing billing problems",
            assignee=None,
            reporter="reporter_id",
            priority=1,
            labels=["customer"],
            platform="web",
            business_impact="high",
            suggested_team_routing="support-team",
            zendesk_ticket_id="ZD-456",
            incident_category="billing-issue",
        )

        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_feature_request(self, mock_jira_client):
        """Test create_issue_feature_request function."""
        mock_issue = {"id": "FEAT-123"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_feature_request(
            title="New Feature",
            description="Feature description",
            reporter="reporter_id",
            priority=2,
            labels=["enhancement"],
            platform="mobile",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        assert call_args[1]["issuetype"] == "Feature Request"
        assert call_args[1]["summary"] == "New Feature"
        assert call_args[1]["description"] == "Feature description"
        assert call_args[1]["reporter"] == "reporter_id"
        assert call_args[1]["priority"] == 2

        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_feature_request_with_none_labels(self, mock_jira_client):
        """Test create_issue_feature_request with None labels (covers line 75)."""
        mock_issue = {"id": "FEAT-124"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_feature_request(
            title="Feature with None labels",
            description="Feature description",
            reporter="reporter_id",
            priority=1,
            labels=None,  # This will trigger line 75: labels = [""]
            platform="web",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        # Should have default labels + feature-request
        expected_labels = ["", "feature-request"]
        assert call_args[1]["labels"] == expected_labels
        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_feature_request_with_existing_label(self, mock_jira_client):
        """Test create_issue_feature_request when label already exists (covers branch 76->78)."""
        mock_issue = {"id": "FEAT-125"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_feature_request(
            title="Feature with existing label",
            description="Feature description",
            reporter="reporter_id",
            priority=1,
            labels=["custom", "feature-request"],  # Already has feature-request
            platform="web",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        # Should not duplicate the feature-request label
        expected_labels = ["custom", "feature-request"]
        assert call_args[1]["labels"] == expected_labels
        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_documentation_request(self, mock_jira_client):
        """Test create_issue_documentation_request function."""
        mock_issue = {"id": "DOC-123"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_documentation_request(
            title="Update Documentation",
            description="Documentation needs updating",
            reporter="reporter_id",
            priority=3,
            labels=["docs"],
            platform="web",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        assert call_args[1]["issuetype"] == "Documentation/Process Request"
        assert call_args[1]["summary"] == "Update Documentation"

        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_documentation_request_with_none_labels(self, mock_jira_client):
        """Test create_issue_documentation_request with None labels (covers line 111)."""
        mock_issue = {"id": "DOC-124"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_documentation_request(
            title="Doc with None labels",
            description="Documentation description",
            reporter="reporter_id",
            priority=2,
            labels=None,  # This will trigger line 111: labels = [""]
            platform="mobile",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        # Should have default labels + documentation-request
        expected_labels = ["", "documentation-request"]
        assert call_args[1]["labels"] == expected_labels
        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_documentation_request_with_existing_label(self, mock_jira_client):
        """Test create_issue_documentation_request when label already exists (covers branch 112->114)."""
        mock_issue = {"id": "DOC-125"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_documentation_request(
            title="Doc with existing label",
            description="Documentation description",
            reporter="reporter_id",
            priority=2,
            labels=["help", "documentation-request"],  # Already has documentation-request
            platform="mobile",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        # Should not duplicate the documentation-request label
        expected_labels = ["help", "documentation-request"]
        assert call_args[1]["labels"] == expected_labels
        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_internal(self, mock_jira_client):
        """Test create_issue_internal function."""
        mock_issue = {"id": "INT-123"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_internal(
            title="Internal Issue",
            description="Internal issue description",
            reporter="reporter_id",
            priority=1,
            labels=["internal"],
            platform="api",
            business_impact="critical",
            team_to_be_routed="backend-team",
            incident_category="infrastructure",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        assert call_args[1]["issuetype"] == "Incident"
        assert call_args[1]["summary"] == "Internal Issue"

        assert result == mock_issue

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_seller(self, mock_jira_client):
        """Test create_issue_seller function."""
        mock_issue = {"id": "SELL-123"}
        mock_jira_client.create_issue.return_value = mock_issue

        result = create_issue_seller(
            title="Seller Issue",
            description="Seller issue description",
            reporter="reporter_id",
            priority=2,
            labels=["seller"],
            platform="web",
            business_impact="medium",
            team_to_be_routed="seller-team",
            incident_category="marketplace",
            seller_contract_id="CONTRACT-123",
            is_key_account=True,
            is_seller_in_golden_list=False,
            zoho_desk_ticket_id="ZOHO-456",
        )

        mock_jira_client.create_issue.assert_called_once()
        call_args = mock_jira_client.create_issue.call_args
        assert call_args[1]["issuetype"] == "Incident"
        assert call_args[1]["summary"] == "Seller Issue"

        assert result == mock_issue


@pytest.mark.django_db
class TestCreateIssueErrorHandling:
    """Test error handling in create_issue functions."""

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_customer_with_jira_client_returning_none(self, mock_jira_client):
        """Test create_issue_customer when jira_client returns None."""
        mock_jira_client.create_issue.return_value = None

        issue_data = CustomerIssueData(
            priority=1,
            labels=["test"],
            platform="web",
            business_impact="low",
            team_to_be_routed="test-team",
            area="test",
            zendesk_ticket_id="123",
        )

        with pytest.raises(AttributeError):
            create_issue_customer(
                title="Test",
                description="Test description",
                reporter="test_reporter",
                issue_data=issue_data,
            )

    @patch("firefighter.raid.service.jira_client")
    def test_create_issue_customer_with_empty_issue_data(self, mock_jira_client):
        """Test create_issue_customer with minimal issue_data."""
        mock_issue = {"id": "TEST-123"}
        mock_jira_client.create_issue.return_value = mock_issue

        issue_data = CustomerIssueData(
            priority=None,
            labels=None,
            platform="test",
            business_impact=None,
            team_to_be_routed=None,
            area=None,
            zendesk_ticket_id=None,
        )

        result = create_issue_customer(
            title="Minimal Test",
            description="Minimal test description",
            reporter="test_reporter",
            issue_data=issue_data,
        )

        # Should still work with None values
        mock_jira_client.create_issue.assert_called_once()
        assert result == mock_issue
