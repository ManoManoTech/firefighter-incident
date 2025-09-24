"""Improved tests for raid.client module focusing on coverage."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from httpx import HTTPError
from jira.exceptions import JIRAError

from firefighter.raid.client import JiraAttachmentError, RaidJiraClient
from firefighter.raid.models import FeatureTeam


class TestJiraAttachmentError:
    """Test JiraAttachmentError exception."""

    def test_jira_attachment_error_creation(self):
        """Test creating JiraAttachmentError."""
        error = JiraAttachmentError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


@pytest.mark.django_db
class TestRaidJiraClientBasics:
    """Test basic RaidJiraClient functionality."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create a minimal mock RaidJiraClient."""
        with patch(
            "firefighter.jira_app.client.JiraClient.__init__", return_value=None
        ):
            client = RaidJiraClient()
            client.jira = Mock()
            return client

    def test_get_projects(self, mock_jira_client):
        """Test get_projects method."""
        mock_projects = [Mock(key="PROJ1"), Mock(key="PROJ2")]
        mock_jira_client.jira.projects.return_value = mock_projects

        result = mock_jira_client.get_projects()

        mock_jira_client.jira.projects.assert_called_once()
        assert result == mock_projects

    def test_create_issue_basic_success(self, mock_jira_client):
        """Test basic create_issue success."""
        # Mock a JIRA issue response with .raw attribute
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Bug",
            summary="Test bug",
            description="Bug description",
            assignee=None,
            reporter="test_reporter",
            priority=1,
        )

        mock_jira_client.jira.create_issue.assert_called_once()
        assert result["id"] == 12345
        assert result["key"] == "TEST-123"

    def test_create_issue_with_valid_business_impact(self, mock_jira_client):
        """Test create_issue with valid business impact values."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12346",
            "key": "TEST-124",
            "fields": {
                "summary": "Test story",
                "description": "Test description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Story"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        # Test each valid business impact value
        for impact in ["Lowest", "Low", "Medium", "High", "Highest"]:
            result = mock_jira_client.create_issue(
                issuetype="Story",
                summary="Test story",
                description="Test description",
                assignee=None,
                reporter="test_reporter",
                priority=2,
                business_impact=impact,
            )
            assert result["id"] == 12346

    def test_create_issue_with_invalid_business_impact(self, mock_jira_client):
        """Test create_issue with invalid business impact."""
        with pytest.raises(ValueError, match="Business impact must be"):
            mock_jira_client.create_issue(
                issuetype="Bug",
                summary="Test bug",
                description="Bug description",
                assignee=None,
                reporter="test_reporter",
                priority=1,
                business_impact="Invalid",
            )

    def test_create_issue_with_na_business_impact(self, mock_jira_client):
        """Test create_issue with N/A business impact (should be ignored)."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12347",
            "key": "TEST-125",
            "fields": {
                "summary": "Test task",
                "description": "Task description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Task"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Task",
            summary="Test task",
            description="Task description",
            assignee=None,
            reporter="test_reporter",
            priority=3,
            business_impact="N/A",
        )

        assert result["id"] == 12347

    def test_create_issue_with_assignee(self, mock_jira_client):
        """Test create_issue with assignee."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12348",
            "key": "TEST-126",
            "fields": {
                "summary": "Test task",
                "description": "Task description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Task"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Task",
            summary="Test task",
            description="Task description",
            assignee="assignee123",
            reporter="test_reporter",
            priority=1,
        )

        assert result["id"] == 12348

    def test_create_issue_with_none_labels(self, mock_jira_client):
        """Test create_issue with None labels (should default to empty string)."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12349",
            "key": "TEST-127",
            "fields": {
                "summary": "Test task",
                "description": "Task description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Task"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Task",
            summary="Test task",
            description="Task description",
            assignee=None,
            reporter="test_reporter",
            priority=None,  # Test None priority
            labels=None,
        )

        assert result["id"] == 12349

    def test_create_issue_with_invalid_priority(self, mock_jira_client):
        """Test create_issue with invalid priority."""
        with pytest.raises(ValueError, match="Priority must be between 1 and 5"):
            mock_jira_client.create_issue(
                issuetype="Bug",
                summary="Test bug",
                description="Bug description",
                assignee=None,
                reporter="test_reporter",
                priority=6,  # Invalid priority
            )

    def test_create_issue_with_all_extra_fields(self, mock_jira_client):
        """Test create_issue with all extra fields."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12350",
            "key": "TEST-128",
            "fields": {
                "summary": "Test comprehensive",
                "description": "Comprehensive description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Story"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Story",
            summary="Test comprehensive",
            description="Base description",
            assignee="assignee123",
            reporter="test_reporter",
            priority=2,
            labels=["label1", "label2"],
            zoho_desk_ticket_id="12345",
            zendesk_ticket_id="67890",
            is_seller_in_golden_list=True,
            is_key_account=True,
            seller_contract_id=999,
            suggested_team_routing="TeamA",
            business_impact="High",
            platform="platform-web",
            environments=["production", "staging"],
            incident_category="Performance",
        )

        assert result["id"] == 12350

    @patch("firefighter.raid.models.FeatureTeam.objects.get")
    def test_create_issue_with_feature_team_routing(
        self, mock_feature_team_get, mock_jira_client
    ):
        """Test create_issue with suggested_team_routing that maps to FeatureTeam."""
        # Mock FeatureTeam
        mock_feature_team = Mock()
        mock_feature_team.jira_project_key = "CUSTOM-PROJ"
        mock_feature_team_get.return_value = mock_feature_team

        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12351",
            "key": "CUSTOM-129",
            "fields": {
                "summary": "Custom project issue",
                "description": "Custom description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Story"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Story",
            summary="Custom project issue",
            description="Custom description",
            assignee=None,
            reporter="test_reporter",
            priority=1,
            suggested_team_routing="CustomTeam",
            project=None,  # Force the method to look up FeatureTeam
        )

        mock_feature_team_get.assert_called_once_with(name="CustomTeam")
        assert result["id"] == 12351

    @patch("firefighter.raid.models.FeatureTeam.objects.get")
    def test_create_issue_with_nonexistent_feature_team(
        self, mock_feature_team_get, mock_jira_client
    ):
        """Test create_issue with suggested_team_routing for nonexistent FeatureTeam."""
        # Mock FeatureTeam.DoesNotExist
        mock_feature_team_get.side_effect = FeatureTeam.DoesNotExist()

        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12352",
            "key": "DEFAULT-130",
            "fields": {
                "summary": "Default project issue",
                "description": "Default description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Bug",
            summary="Default project issue",
            description="Default description",
            assignee=None,
            reporter="test_reporter",
            priority=1,
            suggested_team_routing="NonexistentTeam",
            project=None,  # Force the method to look up FeatureTeam
        )

        mock_feature_team_get.assert_called_once_with(name="NonexistentTeam")
        assert result["id"] == 12352

    def test_create_issue_with_explicit_project(self, mock_jira_client):
        """Test create_issue with explicit project (skips FeatureTeam lookup)."""
        mock_issue = Mock()
        mock_issue.raw = {
            "id": "12353",
            "key": "EXPLICIT-131",
            "fields": {
                "summary": "Explicit project issue",
                "description": "Explicit description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Task"},
            },
        }
        mock_jira_client.jira.create_issue.return_value = mock_issue

        result = mock_jira_client.create_issue(
            issuetype="Task",
            summary="Explicit project issue",
            description="Explicit description",
            assignee=None,
            reporter="test_reporter",
            priority=1,
            suggested_team_routing="SomeTeam",
            project="EXPLICIT-PROJ",  # Explicit project bypasses FeatureTeam lookup
        )

        assert result["id"] == 12353

    def test_create_issue_with_jira_error(self, mock_jira_client):
        """Test create_issue when JIRA raises an error."""
        mock_jira_client.jira.create_issue.side_effect = JIRAError("JIRA error")

        with pytest.raises(JIRAError):
            mock_jira_client.create_issue(
                issuetype="Bug",
                summary="Failed bug",
                description="Bug description",
                assignee=None,
                reporter="test_reporter",
                priority=1,
            )

    def test_jira_object_static_method(self):
        """Test _jira_object static method."""
        test_issue = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }

        result = RaidJiraClient._jira_object(test_issue)

        assert result["id"] == 12345
        assert result["key"] == "TEST-123"
        assert result["summary"] == "Test issue"
        assert result["description"] == "Test description"

    def test_jira_object_invalid_type(self):
        """Test _jira_object with invalid input type."""
        with pytest.raises(AttributeError):
            RaidJiraClient._jira_object("invalid_input")

    def test_jira_object_missing_id(self):
        """Test _jira_object with missing ID."""
        test_issue = {
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }

        with pytest.raises(TypeError, match="Jira ID not found"):
            RaidJiraClient._jira_object(test_issue)

    def test_jira_object_missing_required_fields(self):
        """Test _jira_object with missing required fields."""
        test_issue = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "description": None,  # Missing description
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }

        with pytest.raises(TypeError, match="Jira object has wrong type"):
            RaidJiraClient._jira_object(test_issue)

    def test_jira_object_missing_key(self):
        """Test _jira_object with missing key."""
        test_issue = {
            "id": "12345",
            "key": None,
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "assignee": {"accountId": "assignee123"},
                "reporter": {"accountId": "reporter123"},
                "issuetype": {"name": "Bug"},
            },
        }

        with pytest.raises(TypeError, match="Jira key is None"):
            RaidJiraClient._jira_object(test_issue)


@pytest.mark.django_db
class TestRaidJiraClientAttachments:
    """Test attachment functionality."""

    @patch("firefighter.raid.client.HttpClient")
    @patch("firefighter.raid.client.client")
    def test_add_attachments_success(self, mock_client, mock_http_client_class):
        """Test successful attachment addition."""
        # Setup HTTP client mock
        mock_http_client = Mock()
        mock_http_client_class.return_value = mock_http_client

        mock_response = Mock()
        mock_response.content = b"fake file content"
        mock_response.headers = {"content-type": "image/png"}
        mock_http_client.get.return_value = mock_response

        # Setup JIRA mock
        mock_client.jira.add_attachment.return_value = Mock()

        # Test the method
        RaidJiraClient.add_attachments_to_issue(
            "TEST-123", ["https://example.com/image.png"]
        )

        mock_http_client.get.assert_called_once_with("https://example.com/image.png")
        mock_client.jira.add_attachment.assert_called_once()

    @patch("firefighter.raid.client.HttpClient")
    def test_add_attachments_http_error(self, mock_http_client_class):
        """Test attachment with HTTP error."""
        mock_http_client = Mock()
        mock_http_client_class.return_value = mock_http_client
        mock_http_client.get.side_effect = HTTPError("Network error")

        with pytest.raises(
            JiraAttachmentError, match="Error while adding attachment to issue"
        ):
            RaidJiraClient.add_attachments_to_issue(
                "TEST-123", ["https://bad-url.com/file.png"]
            )

    @patch("firefighter.raid.client.HttpClient")
    @patch("firefighter.raid.client.client")
    def test_add_attachments_jira_error(self, mock_client, mock_http_client_class):
        """Test attachment with JIRA error."""
        # Setup HTTP client mock
        mock_http_client = Mock()
        mock_http_client_class.return_value = mock_http_client

        mock_response = Mock()
        mock_response.content = b"file content"
        mock_response.headers = {"content-type": "text/plain"}
        mock_http_client.get.return_value = mock_response

        # Setup JIRA to fail
        mock_client.jira.add_attachment.side_effect = JIRAError(
            "JIRA attachment failed"
        )

        with pytest.raises(
            JiraAttachmentError, match="Error while adding attachment to issue"
        ):
            RaidJiraClient.add_attachments_to_issue(
                "TEST-123", ["https://example.com/file.txt"]
            )


@pytest.mark.django_db
class TestRaidJiraClientWorkflow:
    """Test workflow and configuration methods."""

    @pytest.fixture
    def workflow_client(self):
        """Create client for workflow testing."""
        with patch(
            "firefighter.jira_app.client.JiraClient.__init__", return_value=None
        ):
            client = RaidJiraClient()
            client.jira = Mock()
            return client

    def test_close_issue(self, workflow_client):
        """Test close_issue method."""
        mock_result = Mock()

        # Mock the workflow method
        workflow_client.transition_issue_auto = Mock(return_value=mock_result)

        result = workflow_client.close_issue("WORKFLOW-123")

        workflow_client.transition_issue_auto.assert_called_once_with(
            "WORKFLOW-123", "Closed", "Incident workflow - v2023.03.13"
        )
        assert result == mock_result

    def test_get_project_config_workflow(self, workflow_client):
        """Test _get_project_config_workflow method."""
        # Mock the base method
        workflow_client._get_project_config_workflow_base = Mock(
            return_value={"workflows": [{"name": "test_workflow"}]}
        )

        result = workflow_client._get_project_config_workflow("TEST")

        workflow_client._get_project_config_workflow_base.assert_called_once_with(
            "TEST", "Incident workflow - v2023.03.13"
        )
        assert "workflows" in result

    def test_get_project_config_workflow_from_builder(self, workflow_client):
        """Test _get_project_config_workflow_from_builder method."""
        # Mock the base method
        workflow_client._get_project_config_workflow_from_builder_base = Mock(
            return_value={"workflows": [{"name": "builder_workflow"}]}
        )

        result = workflow_client._get_project_config_workflow_from_builder()

        workflow_client._get_project_config_workflow_from_builder_base.assert_called_once_with(
            "Incident workflow - v2023.03.13"
        )
        assert result == {"workflows": [{"name": "builder_workflow"}]}

    def test_get_project_config_workflow_from_builder_error(self, workflow_client):
        """Test builder method with HTTP error."""
        # Mock the base method to raise an error
        workflow_client._get_project_config_workflow_from_builder_base = Mock(
            side_effect=HTTPError("HTTP error")
        )

        with pytest.raises(HTTPError):
            workflow_client._get_project_config_workflow_from_builder()
