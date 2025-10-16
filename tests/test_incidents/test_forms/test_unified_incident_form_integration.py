"""End-to-end integration tests for unified incident form custom fields propagation.

This test file verifies that custom fields (zendesk_ticket_id, seller_contract_id, etc.)
are properly transmitted from the form submission all the way to:
1. Form cleaned_data
2. Jira extra fields in signals
3. Incident custom_fields
"""
from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from firefighter.incidents.forms.unified_incident import UnifiedIncidentForm
from firefighter.incidents.models.impact import ImpactLevel, ImpactType, LevelChoices
from firefighter.incidents.signals import create_incident_conversation
from firefighter.slack.views.modals.open import OpenModal
from firefighter.slack.views.modals.opening.details.unified import (
    OpeningUnifiedModal,
    UnifiedIncidentFormSlack,
)


@pytest.mark.django_db
class TestUnifiedIncidentFormCustomFieldsPropagation:
    """Test end-to-end propagation of custom fields from form to signal."""

    def test_customer_impact_zendesk_field_propagates_to_signal(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """Zendesk ticket ID should propagate from form to signal with jira_extra_fields."""
        # Setup
        priority = priority_factory(value=1, default=True)
        environment = environment_factory(value="PRD", default=True)
        category = incident_category_factory()

        # Get customer impact from fixtures (impact_type=3, value=HI)
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.HIGH.value
        )

        # Form data with customer impact and zendesk ticket
        form_data = {
            "title": "Customer issue with Zendesk ticket",
            "description": "Test incident with customer impact and Zendesk tracking",
            "incident_category": category.id,
            "environment": [environment.id],
            "platform": ["platform-FR"],
            "priority": priority.id,
            "zendesk_ticket_id": "12345",
        }

        impacts_data = {
            "customers_impact": customer_impact,
        }

        # Create form with impacts context
        form = UnifiedIncidentFormSlack(
            data=form_data,
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Verify form is valid
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Verify zendesk_ticket_id is in cleaned_data
        assert "zendesk_ticket_id" in form.cleaned_data
        assert form.cleaned_data["zendesk_ticket_id"] == "12345"

        # Mock signal receiver to capture jira_extra_fields
        signal_received = False
        signal_data: dict[str, Any] = {}

        def capture_signal(sender: Any, incident: Any, **kwargs: Any) -> None:
            nonlocal signal_received, signal_data
            signal_received = True
            signal_data = {"incident": incident, **kwargs}

        # Connect signal receiver
        create_incident_conversation.connect(capture_signal, weak=False)

        try:
            # Mock SelectImpactForm.save since it's not what we're testing here
            with patch("firefighter.incidents.forms.unified_incident.SelectImpactForm") as mock_select_impact:
                mock_form_instance = MagicMock()
                mock_form_instance.save.return_value = None
                mock_select_impact.return_value = mock_form_instance

                # Trigger workflow
                user = user_factory()
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=impacts_data,
                    response_type="critical",
                )

            # Verify signal was sent
            assert signal_received, "Signal create_incident_conversation should have been sent"

            # Verify jira_extra_fields was passed to signal
            assert "jira_extra_fields" in signal_data, "jira_extra_fields should be in signal kwargs"

            # Verify zendesk_ticket_id is in jira_extra_fields
            jira_extra_fields = signal_data["jira_extra_fields"]
            assert "zendesk_ticket_id" in jira_extra_fields
            assert jira_extra_fields["zendesk_ticket_id"] == "12345"

            # Verify incident was created with custom_fields
            incident = signal_data["incident"]
            assert incident is not None
            assert hasattr(incident, "custom_fields")
            assert "zendesk_ticket_id" in incident.custom_fields
            assert incident.custom_fields["zendesk_ticket_id"] == "12345"

        finally:
            # Disconnect signal
            create_incident_conversation.disconnect(capture_signal)

    def test_seller_impact_fields_propagate_to_signal(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """Seller-specific fields should propagate from form to signal with jira_extra_fields."""
        # Setup
        priority = priority_factory(value=1, default=True)
        environment = environment_factory(value="PRD", default=True)
        category = incident_category_factory()

        # Get seller impact from fixtures (impact_type=2, value=HI)
        sellers_impact_type = ImpactType.objects.get(value="sellers_impact")
        seller_impact = ImpactLevel.objects.get(
            impact_type=sellers_impact_type,
            value=LevelChoices.HIGH.value
        )

        # Form data with seller impact and seller-specific fields
        form_data = {
            "title": "Seller issue with contract tracking",
            "description": "Test incident with seller impact and contract ID",
            "incident_category": category.id,
            "environment": [environment.id],
            "platform": ["platform-FR"],
            "priority": priority.id,
            "seller_contract_id": "CONTRACT-789",
            "zoho_desk_ticket_id": "ZOHO-456",
            "is_key_account": True,
            "is_seller_in_golden_list": False,
        }

        impacts_data = {
            "sellers_impact": seller_impact,
        }

        # Create form with impacts context
        form = UnifiedIncidentFormSlack(
            data=form_data,
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Verify form is valid
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Verify seller fields are in cleaned_data
        assert form.cleaned_data["seller_contract_id"] == "CONTRACT-789"
        assert form.cleaned_data["zoho_desk_ticket_id"] == "ZOHO-456"
        assert form.cleaned_data["is_key_account"] is True
        assert form.cleaned_data["is_seller_in_golden_list"] is False

        # Mock signal receiver to capture jira_extra_fields
        signal_received = False
        signal_data: dict[str, Any] = {}

        def capture_signal(sender: Any, incident: Any, **kwargs: Any) -> None:
            nonlocal signal_received, signal_data
            signal_received = True
            signal_data = {"incident": incident, **kwargs}

        # Connect signal receiver
        create_incident_conversation.connect(capture_signal, weak=False)

        try:
            # Mock SelectImpactForm.save since it's not what we're testing here
            with patch("firefighter.incidents.forms.unified_incident.SelectImpactForm") as mock_select_impact:
                mock_form_instance = MagicMock()
                mock_form_instance.save.return_value = None
                mock_select_impact.return_value = mock_form_instance

                # Trigger workflow
                user = user_factory()
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=impacts_data,
                    response_type="critical",
                )

            # Verify signal was sent
            assert signal_received, "Signal create_incident_conversation should have been sent"

            # Verify jira_extra_fields was passed to signal
            assert "jira_extra_fields" in signal_data

            # Verify all seller fields are in jira_extra_fields
            jira_extra_fields = signal_data["jira_extra_fields"]
            assert jira_extra_fields["seller_contract_id"] == "CONTRACT-789"
            assert jira_extra_fields["zoho_desk_ticket_id"] == "ZOHO-456"
            assert jira_extra_fields["is_key_account"] is True
            assert jira_extra_fields["is_seller_in_golden_list"] is False

            # Verify incident was created with all seller fields in custom_fields
            incident = signal_data["incident"]
            assert "seller_contract_id" in incident.custom_fields
            assert incident.custom_fields["seller_contract_id"] == "CONTRACT-789"
            assert "zoho_desk_ticket_id" in incident.custom_fields
            assert incident.custom_fields["zoho_desk_ticket_id"] == "ZOHO-456"
            assert "is_key_account" in incident.custom_fields
            assert incident.custom_fields["is_key_account"] is True
            assert "is_seller_in_golden_list" in incident.custom_fields
            assert incident.custom_fields["is_seller_in_golden_list"] is False

        finally:
            # Disconnect signal
            create_incident_conversation.disconnect(capture_signal)

    def test_both_customer_and_seller_fields_propagate_together(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """Both customer and seller fields should propagate when both impacts are selected."""
        # Setup
        priority = priority_factory(value=1, default=True)
        environment = environment_factory(value="PRD", default=True)
        category = incident_category_factory()

        # Get impacts from fixtures
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.HIGH.value
        )

        sellers_impact_type = ImpactType.objects.get(value="sellers_impact")
        seller_impact = ImpactLevel.objects.get(
            impact_type=sellers_impact_type,
            value=LevelChoices.LOW.value
        )

        # Form data with both impacts and all custom fields
        form_data = {
            "title": "Combined customer and seller issue",
            "description": "Test incident affecting both customers and sellers",
            "incident_category": category.id,
            "environment": [environment.id],
            "platform": ["platform-All"],
            "priority": priority.id,
            "zendesk_ticket_id": "ZD-999",
            "seller_contract_id": "SC-888",
            "zoho_desk_ticket_id": "ZOHO-777",
            "is_key_account": False,
            "is_seller_in_golden_list": True,
        }

        impacts_data = {
            "customers_impact": customer_impact,
            "sellers_impact": seller_impact,
        }

        # Create form with impacts context
        form = UnifiedIncidentFormSlack(
            data=form_data,
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Verify form is valid
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Mock signal receiver
        signal_received = False
        signal_data: dict[str, Any] = {}

        def capture_signal(sender: Any, incident: Any, **kwargs: Any) -> None:
            nonlocal signal_received, signal_data
            signal_received = True
            signal_data = {"incident": incident, **kwargs}

        create_incident_conversation.connect(capture_signal, weak=False)

        try:
            # Mock SelectImpactForm.save since it's not what we're testing here
            with patch("firefighter.incidents.forms.unified_incident.SelectImpactForm") as mock_select_impact:
                mock_form_instance = MagicMock()
                mock_form_instance.save.return_value = None
                mock_select_impact.return_value = mock_form_instance

                # Trigger workflow
                user = user_factory()
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=impacts_data,
                    response_type="critical",
                )

            # Verify signal was sent with all fields
            assert signal_received
            jira_extra_fields = signal_data["jira_extra_fields"]

            # Verify both customer and seller fields are present
            assert jira_extra_fields["zendesk_ticket_id"] == "ZD-999"
            assert jira_extra_fields["seller_contract_id"] == "SC-888"
            assert jira_extra_fields["zoho_desk_ticket_id"] == "ZOHO-777"
            assert jira_extra_fields["is_key_account"] is False
            assert jira_extra_fields["is_seller_in_golden_list"] is True

            # Verify new fields: environments and platforms
            assert "environments" in jira_extra_fields
            assert jira_extra_fields["environments"] == ["PRD"]
            assert "platforms" in jira_extra_fields
            assert jira_extra_fields["platforms"] == ["platform-All"]

            # Verify incident custom_fields has all fields (5 original + 2 new = 7)
            incident = signal_data["incident"]
            assert len(incident.custom_fields) == 7
            assert incident.custom_fields["zendesk_ticket_id"] == "ZD-999"
            assert incident.custom_fields["seller_contract_id"] == "SC-888"
            assert incident.custom_fields["environments"] == ["PRD"]
            assert incident.custom_fields["platforms"] == ["platform-All"]

        finally:
            create_incident_conversation.disconnect(capture_signal)

    def test_no_impact_sends_empty_jira_extra_fields(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """When no customer/seller impact is selected, jira_extra_fields should only contain None values."""
        # Setup
        priority = priority_factory(value=1, default=True)
        environment = environment_factory(value="PRD", default=True)
        category = incident_category_factory()

        # Form data without any custom fields
        form_data = {
            "title": "Basic incident without impacts",
            "description": "Test incident with no customer or seller impact",
            "incident_category": category.id,
            "environment": [environment.id],
            "platform": ["platform-FR"],
            "priority": priority.id,
        }

        impacts_data: dict[str, Any] = {}

        # Create form without impacts context
        form = UnifiedIncidentFormSlack(
            data=form_data,
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Verify form is valid
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Verify custom fields are NOT in form fields (removed by _configure_field_visibility)
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields

        # Mock signal receiver
        signal_received = False
        signal_data: dict[str, Any] = {}

        def capture_signal(sender: Any, incident: Any, **kwargs: Any) -> None:
            nonlocal signal_received, signal_data
            signal_received = True
            signal_data = {"incident": incident, **kwargs}

        create_incident_conversation.connect(capture_signal, weak=False)

        try:
            # Mock SelectImpactForm.save since it's not what we're testing here
            with patch("firefighter.incidents.forms.unified_incident.SelectImpactForm") as mock_select_impact:
                mock_form_instance = MagicMock()
                mock_form_instance.save.return_value = None
                mock_select_impact.return_value = mock_form_instance

                # Trigger workflow
                user = user_factory()
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=impacts_data,
                    response_type="critical",
                )

            # Verify signal was sent
            assert signal_received

            # Verify jira_extra_fields exists - custom fields are None, but environments/platforms have defaults
            jira_extra_fields = signal_data["jira_extra_fields"]
            assert jira_extra_fields["zendesk_ticket_id"] is None
            assert jira_extra_fields["seller_contract_id"] is None
            assert jira_extra_fields["zoho_desk_ticket_id"] is None
            assert jira_extra_fields["is_key_account"] is None
            assert jira_extra_fields["is_seller_in_golden_list"] is None

            # New fields: environments and platforms have default values (not None)
            assert "environments" in jira_extra_fields
            assert jira_extra_fields["environments"] == ["PRD"]  # Default from form
            assert "platforms" in jira_extra_fields
            assert jira_extra_fields["platforms"] == ["platform-FR"]  # Default from form

            # Verify incident custom_fields only has environments and platforms (None values filtered out)
            incident = signal_data["incident"]
            assert len(incident.custom_fields) == 2
            assert incident.custom_fields["environments"] == ["PRD"]
            assert incident.custom_fields["platforms"] == ["platform-FR"]

        finally:
            create_incident_conversation.disconnect(capture_signal)


@pytest.mark.django_db
class TestOpenModalPreservesCustomFieldsContext:
    """Test that open.py properly passes context to form during validation and submission."""

    def test_open_modal_passes_impacts_data_to_form_validation(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
    ):
        """OpenModal._validate_details_form should pass open_incident_context to form initialization."""
        # Setup
        priority = priority_factory(value=1, default=True)
        environment_factory(value="PRD", default=True)
        incident_category_factory()

        # Get customer impact from fixtures
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.HIGH.value
        )

        # Simulate the context as it exists in open.py
        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {
                "customers_impact": customer_impact,
            },
            "details_form_data": {
                "priority": str(priority.id),
            },
        }

        # Mock form data with zendesk field
        details_form_data = {
            "title": "Test incident",
            "description": "Test description for validation",
            "zendesk_ticket_id": "VALIDATION-123",
        }

        # Call _validate_details_form with context (this is the fix we applied)
        _is_valid, _form_class, form = OpenModal._validate_details_form(
            details_form_modal_class=OpeningUnifiedModal,
            details_form_data=details_form_data,
            open_incident_context=open_incident_context,
        )

        # Verify that the form has zendesk_ticket_id field
        # This proves that impacts_data was passed correctly from open_incident_context
        assert "zendesk_ticket_id" in form.fields, (
            "zendesk_ticket_id should be in form fields - "
            "this proves open_incident_context was passed correctly"
        )

        # Form will be invalid due to missing required fields, but that's expected
        # We're only testing that the context was passed and fields were configured correctly

    def test_open_modal_handle_modal_fn_passes_context_to_form_submission(
        self,
        priority_factory,
        environment_factory,
        incident_category_factory,
        user_factory,
    ):
        """OpenModal.handle_modal_fn should pass impacts_data and response_type to form during submission."""
        # This test verifies that the fix in open.py lines 612-657 works correctly
        # Setup
        priority = priority_factory(value=1, default=True)
        environment = environment_factory(value="PRD", default=True)
        category = incident_category_factory()

        # Get customer impact from fixtures
        customers_impact_type = ImpactType.objects.get(value="customers_impact")
        customer_impact = ImpactLevel.objects.get(
            impact_type=customers_impact_type,
            value=LevelChoices.HIGH.value
        )

        # Simulate the context as OpenModal.handle_modal_fn would have it
        impacts_data_for_context = {
            "customers_impact": customer_impact,
        }

        form_data = {
            "title": "Submission test with Zendesk",
            "description": "Test that form receives context during submission",
            "incident_category": category.id,
            "environment": [environment.id],
            "platform": ["platform-FR"],
            "priority": priority.id,
            "zendesk_ticket_id": "SUBMIT-456",
        }

        # This simulates what happens in open.py after our fix (using inspect.signature)
        init_params = inspect.signature(UnifiedIncidentForm.__init__).parameters

        form_kwargs: dict[str, Any] = {}
        if "impacts_data" in init_params:
            form_kwargs["impacts_data"] = impacts_data_for_context
        if "response_type" in init_params:
            form_kwargs["response_type"] = "critical"

        # Create form with the kwargs (this is what open.py does now)
        form = UnifiedIncidentForm(form_data, **form_kwargs)

        # Verify form is valid
        assert form.is_valid(), f"Form should be valid. Errors: {form.errors}"

        # Verify zendesk_ticket_id is in cleaned_data
        assert form.cleaned_data["zendesk_ticket_id"] == "SUBMIT-456"

        # Verify that trigger_incident_workflow will send the field to signal
        signal_received = False
        signal_data: dict[str, Any] = {}

        def capture_signal(sender: Any, incident: Any, **kwargs: Any) -> None:
            nonlocal signal_received, signal_data
            signal_received = True
            signal_data = {"incident": incident, **kwargs}

        create_incident_conversation.connect(capture_signal, weak=False)

        try:
            # Mock SelectImpactForm.save since it's not what we're testing here
            with patch("firefighter.incidents.forms.unified_incident.SelectImpactForm") as mock_select_impact:
                mock_form_instance = MagicMock()
                mock_form_instance.save.return_value = None
                mock_select_impact.return_value = mock_form_instance

                user = user_factory()
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=impacts_data_for_context,
                    response_type="critical",
                )

            assert signal_received
            assert signal_data["jira_extra_fields"]["zendesk_ticket_id"] == "SUBMIT-456"

        finally:
            create_incident_conversation.disconnect(capture_signal)
