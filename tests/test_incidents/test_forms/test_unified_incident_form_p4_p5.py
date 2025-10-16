"""Tests for P4/P5 (normal) incident creation with Jira ticket custom fields.

This test suite verifies that P4/P5 incidents (response_type="normal") properly
pass all custom fields to Jira when creating tickets, including:
- environments (customfield_11049)
- platform (customfield_10201)
- business_impact (customfield_10936)
- customer-specific fields (zendesk_ticket_id)
- seller-specific fields (seller_contract_id, zoho_desk_ticket_id, etc.)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from firefighter.incidents.forms.unified_incident import UnifiedIncidentForm
from firefighter.incidents.models.impact import ImpactLevel, ImpactType, LevelChoices
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import FeatureTeam


@pytest.fixture
def feature_team_payment(db):
    """Create a FeatureTeam for Payment."""
    return FeatureTeam.objects.create(
        id=10915,
        name="Payment",
        jira_project_key="PAY",
    )


@pytest.fixture
def feature_team_seller(db):
    """Create a FeatureTeam for Seller Services."""
    return FeatureTeam.objects.create(
        id=11007,
        name="Seller Services",
        jira_project_key="SELLER",
    )


@pytest.fixture
def feature_team_platform(db):
    """Create a FeatureTeam for Platform."""
    return FeatureTeam.objects.create(
        id=11034,
        name="Platform",
        jira_project_key="PLAT",
    )


@pytest.mark.django_db
class TestP4P5CustomerImpactJiraFields:
    """Test P4/P5 customer impact incidents create Jira tickets with all custom fields."""

    def test_p4_customer_impact_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
        feature_team_payment,
    ):
        """P4 customer impact should create Jira ticket with zendesk, environments, platform, business_impact."""
        # Setup P4 priority
        p4_priority = priority_factory(value=4, name="P4", default=False)
        env_prd = environment_factory(value="PRD", default=True)
        env_stg = environment_factory(value="STG", default=False)
        category = incident_category_factory()
        user = user_factory()

        # Get customer impact
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.LOW.value  # P4 = low impact
        )

        # Form data with customer-specific fields
        form_data = {
            "title": "P4 Customer issue with Zendesk",
            "description": "Test P4 customer incident",
            "incident_category": category.id,
            "environment": [env_prd.id, env_stg.id],  # Multiple environments
            "platform": ["platform-FR", "platform-DE"],  # Multiple platforms
            "priority": p4_priority.id,
            "zendesk_ticket_id": "ZD-12345",
            "suggested_team_routing": feature_team_payment.id,  # Required for P4/P5
        }

        impacts_data = {
            "customers_impact": customer_impact,
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Mock the Jira client to capture what's passed
        with (
            patch("firefighter.raid.service.jira_client.create_issue") as mock_create_issue,
            patch("firefighter.raid.service.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.SelectImpactForm"),
            patch("firefighter.raid.forms.set_jira_ticket_watchers_raid"),
            patch("firefighter.raid.forms.alert_slack_new_jira_ticket"),
            patch("firefighter.raid.forms.JiraTicket.objects.create"),
        ):
            # Mock return value (format from _jira_object, compatible with JiraTicket.objects.create)
            mock_create_issue.return_value = {
                "id": 12345,
                "key": "TEST-123",
                "project_key": "TEST",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test description",
                "summary": "Test summary",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user

            # Trigger workflow
            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="normal",
            )

            # Verify create_issue was called
            assert mock_create_issue.called, "Jira create_issue should have been called"

            # Get the call arguments
            call_kwargs = mock_create_issue.call_args.kwargs

            # ✅ CRITICAL ASSERTIONS - These should FAIL initially
            assert "environments" in call_kwargs, "environments should be passed to Jira"
            assert set(call_kwargs["environments"]) == {"PRD", "STG"}, "Should pass environment values"

            # ✅ Verify platform is passed
            assert "platform" in call_kwargs, "platform should be passed to Jira"
            assert call_kwargs["platform"] == "platform-FR", "Should pass first platform"

            # ✅ Verify business_impact is passed
            assert "business_impact" in call_kwargs, "business_impact should be passed to Jira"
            # Business impact should be computed from customer impact level
            assert call_kwargs["business_impact"] is not None

            # ✅ Verify zendesk_ticket_id is passed
            assert "zendesk_ticket_id" in call_kwargs, "zendesk_ticket_id should be passed"
            assert call_kwargs["zendesk_ticket_id"] == "ZD-12345"

    def test_p5_customer_impact_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
        feature_team_payment,
    ):
        """P5 customer impact should create Jira ticket with all custom fields."""
        # Setup P5 priority
        p5_priority = priority_factory(value=5, name="P5", default=False)
        env_prd = environment_factory(value="PRD", default=True)
        category = incident_category_factory()
        user = user_factory()

        # Get customer impact (lowest for P5)
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.LOWEST.value
        )

        form_data = {
            "title": "P5 Customer cosmetic issue",
            "description": "Test P5 customer incident",
            "incident_category": category.id,
            "environment": [env_prd.id],
            "platform": ["platform-All"],
            "priority": p5_priority.id,
            "zendesk_ticket_id": "ZD-99999",
            "suggested_team_routing": feature_team_payment.id,
        }

        impacts_data = {
            "customers_impact": customer_impact,
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        with (
            patch("firefighter.raid.service.jira_client.create_issue") as mock_create_issue,
            patch("firefighter.raid.service.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.SelectImpactForm"),
            patch("firefighter.raid.forms.set_jira_ticket_watchers_raid"),
            patch("firefighter.raid.forms.alert_slack_new_jira_ticket"),
            patch("firefighter.raid.forms.JiraTicket.objects.create"),
        ):
            mock_create_issue.return_value = {
                "id": 67890,
                "key": "TEST-456",
                "project_key": "TEST",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user

            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="normal",
            )

            call_kwargs = mock_create_issue.call_args.kwargs

            # Critical assertions
            assert "environments" in call_kwargs
            assert call_kwargs["environments"] == ["PRD"]
            assert "platform" in call_kwargs
            assert call_kwargs["platform"] == "platform-All"
            assert "business_impact" in call_kwargs
            assert "zendesk_ticket_id" in call_kwargs
            assert call_kwargs["zendesk_ticket_id"] == "ZD-99999"


@pytest.mark.django_db
class TestP4P5SellerImpactJiraFields:
    """Test P4/P5 seller impact incidents create Jira tickets with all seller custom fields."""

    def test_p4_seller_impact_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
        feature_team_seller,
    ):
        """P4 seller impact should create Jira with seller fields + environments."""
        p4_priority = priority_factory(value=4, name="P4", default=False)
        env_prd = environment_factory(value="PRD", default=True)
        env_int = environment_factory(value="INT", default=False)
        category = incident_category_factory()
        user = user_factory()

        # Get seller impact
        sellers_impact_type = ImpactType.objects.get(value="sellers_impact")
        seller_impact = ImpactLevel.objects.get(
            impact_type=sellers_impact_type,
            value=LevelChoices.LOW.value
        )

        form_data = {
            "title": "P4 Seller contract issue",
            "description": "Test P4 seller incident",
            "incident_category": category.id,
            "environment": [env_prd.id, env_int.id],
            "platform": ["platform-FR"],
            "priority": p4_priority.id,
            "suggested_team_routing": feature_team_seller.id,
            "seller_contract_id": "SC-789",
            "zoho_desk_ticket_id": "ZOHO-456",
            "is_key_account": True,
            "is_seller_in_golden_list": False,
        }

        impacts_data = {
            "sellers_impact": seller_impact,
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        with (
            patch("firefighter.raid.service.jira_client.create_issue") as mock_create_issue,
            patch("firefighter.raid.service.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.SelectImpactForm"),
            patch("firefighter.raid.forms.set_jira_ticket_watchers_raid"),
            patch("firefighter.raid.forms.alert_slack_new_jira_ticket"),
            patch("firefighter.raid.forms.JiraTicket.objects.create"),
        ):
            mock_create_issue.return_value = {
                "id": 11111,
                "key": "SELLER-123",
                "project_key": "SELLER",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user

            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="normal",
            )

            call_kwargs = mock_create_issue.call_args.kwargs

            # ✅ CRITICAL ASSERTIONS for environments
            assert "environments" in call_kwargs, "environments should be passed"
            assert set(call_kwargs["environments"]) == {"PRD", "INT"}, "Should pass all environment values"

            # ✅ Verify seller-specific fields
            assert "seller_contract_id" in call_kwargs
            assert call_kwargs["seller_contract_id"] == "SC-789"
            assert "zoho_desk_ticket_id" in call_kwargs
            assert call_kwargs["zoho_desk_ticket_id"] == "ZOHO-456"
            assert "is_key_account" in call_kwargs
            assert call_kwargs["is_key_account"] is True
            assert "is_seller_in_golden_list" in call_kwargs
            assert call_kwargs["is_seller_in_golden_list"] is False

            # ✅ Verify platform and business_impact
            assert "platform" in call_kwargs
            assert call_kwargs["platform"] == "platform-FR"
            assert "business_impact" in call_kwargs


@pytest.mark.django_db
class TestP4P5InternalImpactJiraFields:
    """Test P4/P5 internal (employee) impact incidents create Jira with all fields."""

    def test_p4_employee_impact_creates_jira_with_environments(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
        feature_team_platform,
    ):
        """P4 employee impact should create Jira with environments."""
        p4_priority = priority_factory(value=4, name="P4", default=False)
        env_stg = environment_factory(value="STG", default=False)
        env_int = environment_factory(value="INT", default=False)
        category = incident_category_factory()
        user = user_factory()

        # Get employee impact
        employees_impact_type = ImpactType.objects.get(value="employees_impact")
        employee_impact = ImpactLevel.objects.get(
            impact_type=employees_impact_type,
            value=LevelChoices.LOW.value
        )

        form_data = {
            "title": "P4 Internal tool degraded",
            "description": "Test P4 internal incident",
            "incident_category": category.id,
            "environment": [env_stg.id, env_int.id],
            "platform": ["platform-Internal"],
            "priority": p4_priority.id,
            "suggested_team_routing": feature_team_platform.id,
        }

        impacts_data = {
            "employees_impact": employee_impact,
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        with (
            patch("firefighter.raid.service.jira_client.create_issue") as mock_create_issue,
            patch("firefighter.raid.service.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.SelectImpactForm"),
            patch("firefighter.raid.forms.set_jira_ticket_watchers_raid"),
            patch("firefighter.raid.forms.alert_slack_new_jira_ticket"),
            patch("firefighter.raid.forms.JiraTicket.objects.create"),
        ):
            mock_create_issue.return_value = {
                "id": 22222,
                "key": "INTERNAL-456",
                "project_key": "INTERNAL",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user

            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="normal",
            )

            call_kwargs = mock_create_issue.call_args.kwargs

            # ✅ CRITICAL: environments must be passed for internal incidents too
            assert "environments" in call_kwargs
            assert set(call_kwargs["environments"]) == {"STG", "INT"}, "Should pass all environment values"

            # ✅ Verify platform and business_impact
            assert "platform" in call_kwargs
            assert call_kwargs["platform"] == "platform-Internal"
            assert "business_impact" in call_kwargs
