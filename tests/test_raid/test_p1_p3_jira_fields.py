"""Tests for P1-P3 (critical) incident Jira ticket creation with all custom fields.

This test suite verifies that P1-P3 incidents properly pass all custom fields
to Jira when creating tickets via the incident_channel_done signal, including:
- environments (customfield_11049)
- platform (customfield_10201)
- business_impact (customfield_10936)
- customer/seller specific fields from jira_extra_fields
"""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from firefighter.incidents.forms.unified_incident import UnifiedIncidentForm
from firefighter.incidents.models.impact import ImpactLevel, ImpactType, LevelChoices
from firefighter.incidents.signals import create_incident_conversation
from firefighter.jira_app.client import client
from firefighter.jira_app.models import JiraUser
from firefighter.raid.signals.incident_created import create_ticket


@pytest.mark.django_db
class TestP1P2P3JiraTicketFields:
    """Test P1-P3 incident Jira ticket creation includes all custom fields."""

    def test_p1_with_customer_impact_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """P1 customer impact should create Jira with zendesk, environments, platform, business_impact."""
        # Setup P1 priority
        p1_priority = priority_factory(value=1, name="P1", default=True)
        env_prd = environment_factory(value="PRD", default=True)
        env_stg = environment_factory(value="STG", default=False)
        category = incident_category_factory()
        user = user_factory()

        # Get customer impact
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.HIGHEST.value
        )

        # Form data
        form_data = {
            "title": "P1 Critical customer issue",
            "description": "Test P1 critical incident",
            "incident_category": category.id,
            "environment": [env_prd.id, env_stg.id],  # Multiple environments!
            "platform": ["platform-FR", "platform-DE"],  # Multiple platforms!
            "priority": p1_priority.id,
            "zendesk_ticket_id": "ZD-CRITICAL-123",
        }

        impacts_data = {
            "customers_impact": customer_impact,  # Pass object for get_business_impact()
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Setup mock channel
        mock_channel = MagicMock()
        mock_channel.channel_id = "C123456"

        # Mock the signal send to intercept kwargs and directly call create_ticket handler
        def mock_signal_send(sender, incident, **kwargs):
            # Skip calling the real signal handler (which would call Slack API)
            # Instead, directly call the JIRA ticket creation handler
            create_ticket(
                sender="test",
                incident=incident,
                channel=mock_channel,
                jira_extra_fields=kwargs.get("jira_extra_fields", {}),
                impacts_data=kwargs.get("impacts_data", {}),
            )

        # Mock Jira client property at the CLASS level to prevent real connection
        mock_jira_client = MagicMock()

        with (
            patch.object(create_incident_conversation, "send", side_effect=mock_signal_send),
            patch.object(type(client), "jira", new_callable=PropertyMock, return_value=mock_jira_client),
            patch("firefighter.raid.signals.incident_created.client.create_issue") as mock_jira_create,
            patch("firefighter.raid.signals.incident_created.client.get_jira_user_from_jira_id") as mock_get_default_jira_user,
            patch("firefighter.raid.signals.incident_created.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.get_business_impact") as mock_get_business_impact,
            patch("firefighter.incidents.forms.unified_incident.SelectImpactForm.save"),
            patch("firefighter.raid.signals.incident_created.JiraTicket.objects.create"),
        ):
            # Mock Jira ticket creation (format from _jira_object)
            mock_jira_create.return_value = {
                "id": 99999,
                "key": "P1-TEST-123",
                "project_key": "P1",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user
            mock_default_jira_user = JiraUser(id="default_account")
            mock_get_default_jira_user.return_value = mock_default_jira_user
            mock_get_business_impact.return_value = "High"

            # Trigger the P1-P3 workflow
            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="critical",
            )

            # Verify Jira create_issue was called
            assert mock_jira_create.called, "Jira create_issue should have been called"

            # Get the call arguments
            call_kwargs = mock_jira_create.call_args.kwargs

            # ✅ CRITICAL ASSERTIONS - These will FAIL initially
            assert "environments" in call_kwargs, "environments should be passed to Jira for P1-P3"
            # P1-P3 use first environment only (from non-deterministic QuerySet order)
            assert len(call_kwargs["environments"]) == 1, "Should pass exactly one environment"
            assert call_kwargs["environments"][0] in {"PRD", "STG"}, "Should pass one of the form environments"

            assert "platform" in call_kwargs, "platform should be passed to Jira for P1-P3"
            assert call_kwargs["platform"] == "platform-FR", "Should pass first platform value"

            assert "business_impact" in call_kwargs, "business_impact should be passed to Jira for P1-P3"
            assert call_kwargs["business_impact"] is not None, "Business impact should be computed from customer impact"

            # Verify zendesk is passed via jira_extra_fields
            assert "zendesk_ticket_id" in call_kwargs
            assert call_kwargs["zendesk_ticket_id"] == "ZD-CRITICAL-123"

    def test_p2_with_seller_impact_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """P2 seller impact should create Jira with seller fields + environments."""
        p2_priority = priority_factory(value=2, name="P2", default=False)
        env_prd = environment_factory(value="PRD", default=True)
        category = incident_category_factory()
        user = user_factory()

        # Get seller impact
        sellers_impact_type = ImpactType.objects.get(value="sellers_impact")
        seller_impact = ImpactLevel.objects.get(
            impact_type=sellers_impact_type,
            value=LevelChoices.HIGH.value
        )

        form_data = {
            "title": "P2 Critical seller issue",
            "description": "Test P2 seller incident",
            "incident_category": category.id,
            "environment": [env_prd.id],
            "platform": ["platform-FR"],
            "priority": p2_priority.id,
            "seller_contract_id": "SC-CRITICAL-999",
            "zoho_desk_ticket_id": "ZOHO-CRITICAL-888",
            "is_key_account": True,
            "is_seller_in_golden_list": True,
        }

        impacts_data = {
            "sellers_impact": seller_impact,  # Pass object for get_business_impact()
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Setup mock channel
        mock_channel = MagicMock()
        mock_channel.channel_id = "C789012"

        # Mock the signal send to intercept kwargs and directly call create_ticket handler
        def mock_signal_send(sender, incident, **kwargs):
            # Skip calling the real signal handler (which would call Slack API)
            # Instead, directly call the JIRA ticket creation handler
            create_ticket(
                sender="test",
                incident=incident,
                channel=mock_channel,
                jira_extra_fields=kwargs.get("jira_extra_fields", {}),
                impacts_data=kwargs.get("impacts_data", {}),
            )

        # Mock Jira client property at the CLASS level to prevent real connection
        mock_jira_client = MagicMock()

        with (
            patch.object(create_incident_conversation, "send", side_effect=mock_signal_send),
            patch.object(type(client), "jira", new_callable=PropertyMock, return_value=mock_jira_client),
            patch("firefighter.raid.signals.incident_created.client.create_issue") as mock_jira_create,
            patch("firefighter.raid.signals.incident_created.client.get_jira_user_from_jira_id") as mock_get_default_jira_user,
            patch("firefighter.raid.signals.incident_created.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.get_business_impact") as mock_get_business_impact,
            patch("firefighter.incidents.forms.unified_incident.SelectImpactForm.save"),
            patch("firefighter.raid.signals.incident_created.JiraTicket.objects.create"),
        ):
            mock_jira_create.return_value = {
                "id": 88888,
                "key": "P2-SELLER-456",
                "project_key": "P2",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user
            mock_default_jira_user = JiraUser(id="default_account")
            mock_get_default_jira_user.return_value = mock_default_jira_user
            mock_get_business_impact.return_value = "High"

            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="critical",
            )

            call_kwargs = mock_jira_create.call_args.kwargs

            # ✅ CRITICAL: environments must be passed with exact value
            assert "environments" in call_kwargs, "environments should be passed to Jira for P2"
            assert call_kwargs["environments"] == ["PRD"], "Should pass environment value"

            # ✅ Verify platform and business_impact with exact values
            assert "platform" in call_kwargs, "platform should be passed to Jira for P2"
            assert call_kwargs["platform"] == "platform-FR", "Should pass platform value"
            assert "business_impact" in call_kwargs, "business_impact should be passed to Jira for P2"
            assert call_kwargs["business_impact"] is not None, "Business impact should be computed"

            # ✅ Verify seller-specific fields
            assert "seller_contract_id" in call_kwargs
            assert call_kwargs["seller_contract_id"] == "SC-CRITICAL-999"
            assert "zoho_desk_ticket_id" in call_kwargs
            assert call_kwargs["zoho_desk_ticket_id"] == "ZOHO-CRITICAL-888"
            assert "is_key_account" in call_kwargs
            assert call_kwargs["is_key_account"] is True
            assert "is_seller_in_golden_list" in call_kwargs
            assert call_kwargs["is_seller_in_golden_list"] is True

    def test_p3_with_both_impacts_creates_jira_with_all_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """P3 with both customer and seller impact should pass all fields to Jira."""
        p3_priority = priority_factory(value=3, name="P3", default=False)
        env_prd = environment_factory(value="PRD", default=True)
        env_stg = environment_factory(value="STG", default=False)
        category = incident_category_factory()
        user = user_factory()

        # Get both impacts
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.MEDIUM.value
        )
        sellers_impact_type = ImpactType.objects.get(value="sellers_impact")
        seller_impact = ImpactLevel.objects.get(
            impact_type=sellers_impact_type,
            value=LevelChoices.LOW.value
        )

        form_data = {
            "title": "P3 Combined customer and seller",
            "description": "Test P3 with multiple impacts",
            "incident_category": category.id,
            "environment": [env_prd.id, env_stg.id],
            "platform": ["platform-All"],
            "priority": p3_priority.id,
            "zendesk_ticket_id": "ZD-P3-111",
            "seller_contract_id": "SC-P3-222",
            "zoho_desk_ticket_id": "ZOHO-P3-333",
            "is_key_account": False,
            "is_seller_in_golden_list": False,
        }

        impacts_data = {
            "customers_impact": customer_impact,  # Pass object for get_business_impact()
            "sellers_impact": seller_impact,  # Pass object for get_business_impact()
        }

        form = UnifiedIncidentForm(form_data)
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Setup mock channel
        mock_channel = MagicMock()
        mock_channel.channel_id = "C111222"

        # Mock the signal send to intercept kwargs and directly call create_ticket handler
        def mock_signal_send(sender, incident, **kwargs):
            # Skip calling the real signal handler (which would call Slack API)
            # Instead, directly call the JIRA ticket creation handler
            create_ticket(
                sender="test",
                incident=incident,
                channel=mock_channel,
                jira_extra_fields=kwargs.get("jira_extra_fields", {}),
                impacts_data=kwargs.get("impacts_data", {}),
            )

        # Mock Jira client property at the CLASS level to prevent real connection
        mock_jira_client = MagicMock()

        with (
            patch.object(create_incident_conversation, "send", side_effect=mock_signal_send),
            patch.object(type(client), "jira", new_callable=PropertyMock, return_value=mock_jira_client),
            patch("firefighter.raid.signals.incident_created.client.create_issue") as mock_jira_create,
            patch("firefighter.raid.signals.incident_created.client.get_jira_user_from_jira_id") as mock_get_default_jira_user,
            patch("firefighter.raid.signals.incident_created.get_jira_user_from_user") as mock_get_jira_user,
            patch("firefighter.raid.forms.get_business_impact") as mock_get_business_impact,
            patch("firefighter.incidents.forms.unified_incident.SelectImpactForm.save"),
            patch("firefighter.raid.signals.incident_created.JiraTicket.objects.create"),
        ):
            mock_jira_create.return_value = {
                "id": 77777,
                "key": "P3-COMBO-789",
                "project_key": "P3",
                "assignee_id": None,
                "reporter_id": "test_account",
                "description": "Test",
                "summary": "Test",
                "issue_type": "Incident",
                "business_impact": "",
            }
            mock_jira_user = JiraUser(id="test_account")
            mock_get_jira_user.return_value = mock_jira_user
            mock_default_jira_user = JiraUser(id="default_account")
            mock_get_default_jira_user.return_value = mock_default_jira_user
            mock_get_business_impact.return_value = "High"

            form.trigger_incident_workflow(
                creator=user,
                impacts_data=impacts_data,
                response_type="critical",
            )

            call_kwargs = mock_jira_create.call_args.kwargs

            # ✅ All fields should be present with exact values
            assert "environments" in call_kwargs, "environments should be passed to Jira for P3"
            # P1-P3 use first environment only (from non-deterministic QuerySet order)
            assert len(call_kwargs["environments"]) == 1, "Should pass exactly one environment"
            assert call_kwargs["environments"][0] in {"PRD", "STG"}, "Should pass one of the form environments"
            assert "platform" in call_kwargs, "platform should be passed to Jira for P3"
            assert call_kwargs["platform"] == "platform-All", "Should pass first platform value"
            assert "business_impact" in call_kwargs, "business_impact should be passed to Jira for P3"
            assert call_kwargs["business_impact"] is not None, "Business impact should be computed"
            assert "zendesk_ticket_id" in call_kwargs
            assert call_kwargs["zendesk_ticket_id"] == "ZD-P3-111"
            assert "seller_contract_id" in call_kwargs
            assert call_kwargs["seller_contract_id"] == "SC-P3-222"
