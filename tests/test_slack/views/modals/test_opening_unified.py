"""Tests for unified incident opening modal."""
from __future__ import annotations

import json

import pytest

from firefighter.incidents.models.impact import LevelChoices
from firefighter.slack.views.modals.base_modal.form_utils import SlackForm
from firefighter.slack.views.modals.opening.details.unified import (
    OpeningUnifiedModal,
    UnifiedIncidentFormSlack,
)


@pytest.mark.django_db
class TestUnifiedIncidentFormSlack:
    """Test Slack-specific version of unified form."""

    def test_form_initializes_with_impacts_and_response_type(
        self, priority_factory, impact_level_factory
    ):
        """Form should properly receive impacts_data and response_type."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        impacts_data = {"customers_impact": customer_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should configure field visibility
        assert "zendesk_ticket_id" in form.fields
        assert "suggested_team_routing" not in form.fields

    def test_slack_blocks_generation_with_multiple_choice_fields(
        self, priority_factory, environment_factory
    ):
        """Slack blocks should generate correctly with multiple choice fields."""
        priority_factory(value=1, default=True)
        environment_factory(value="PRD", default=True)
        environment_factory(value="STG", default=False)

        # Use SlackForm wrapper to generate blocks
        slack_form = SlackForm(UnifiedIncidentFormSlack)(
            impacts_data={},
            response_type="critical",
        )

        # Should generate blocks without errors
        blocks = slack_form.slack_blocks()
        assert len(blocks) > 0

        # Find environment block (multi-select)
        env_blocks = [b for b in blocks if hasattr(b, "block_id") and b.block_id == "environment"]
        assert len(env_blocks) == 1

        env_block = env_blocks[0]
        assert env_block.element.type == "multi_static_select"

    def test_priority_field_is_hidden(self, priority_factory):
        """Priority field should not appear in Slack blocks."""
        priority_factory(value=1, default=True)

        # Use SlackForm wrapper to generate blocks
        slack_form = SlackForm(UnifiedIncidentFormSlack)(
            impacts_data={},
            response_type="critical",
        )

        blocks = slack_form.slack_blocks()

        # Priority field should not generate a block (it's hidden)
        priority_blocks = [
            b for b in blocks if hasattr(b, "block_id") and b.block_id == "priority"
        ]
        assert len(priority_blocks) == 0


@pytest.mark.django_db
class TestOpeningUnifiedModal:
    """Test the unified opening modal."""

    def test_build_modal_fn_passes_context_to_form(
        self, priority_factory, impact_level_factory
    ):
        """build_modal_fn should pass impacts and response_type to form."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {"customers_impact": customer_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should build view without errors
        assert view is not None
        assert view.type == "modal"
        assert len(view.blocks) > 0

        # Check private_metadata contains our context
        metadata = json.loads(view.private_metadata)
        assert metadata["response_type"] == "critical"
        assert "impact_form_data" in metadata

    def test_build_modal_fn_critical_incident_hides_feature_team(
        self, priority_factory
    ):
        """Critical incident should not show feature team field."""
        priority_factory(value=1, default=True)

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Check that feature team field is not in blocks
        feature_team_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "suggested_team_routing"
        ]
        assert len(feature_team_blocks) == 0

    def test_build_modal_fn_normal_incident_shows_feature_team(
        self, priority_factory
    ):
        """Normal incident (P4-P5) should show feature team field."""
        priority_factory(value=4, default=True)

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "normal",
            "impact_form_data": {},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Check that feature team field IS in blocks
        feature_team_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "suggested_team_routing"
        ]
        assert len(feature_team_blocks) == 1

    def test_build_modal_fn_customer_impact_shows_zendesk(
        self, priority_factory, impact_level_factory
    ):
        """Customer impact should show Zendesk field."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {"customers_impact": customer_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Check that zendesk field IS in blocks
        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 1

    def test_build_modal_fn_seller_impact_shows_seller_fields(
        self, priority_factory, impact_level_factory
    ):
        """Seller impact should show seller-specific fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {"sellers_impact": seller_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Check seller fields are in blocks
        seller_contract_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "seller_contract_id"
        ]
        assert len(seller_contract_blocks) == 1

        zoho_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zoho_desk_ticket_id"
        ]
        assert len(zoho_blocks) == 1

    def test_build_modal_fn_business_impact_only_hides_customer_seller_fields(
        self, priority_factory, impact_level_factory
    ):
        """Business impact only should not show customer/seller fields."""
        priority_factory(value=1, default=True)
        business_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Business")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {"business_impact": business_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should NOT show customer or seller fields
        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 0

        seller_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "seller_contract_id"
        ]
        assert len(seller_blocks) == 0

    def test_build_modal_fn_employee_impact_only_hides_customer_seller_fields(
        self, priority_factory, impact_level_factory
    ):
        """Employee impact only should not show customer/seller fields."""
        priority_factory(value=1, default=True)
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {"employees_impact": employee_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should NOT show customer or seller fields
        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 0

        seller_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "seller_contract_id"
        ]
        assert len(seller_blocks) == 0

    def test_build_modal_fn_all_impacts_shows_all_fields(
        self, priority_factory, impact_level_factory
    ):
        """All impact types should show all specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")
        business_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Business")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {
                "customers_impact": customer_impact,
                "sellers_impact": seller_impact,
                "employees_impact": employee_impact,
                "business_impact": business_impact,
            },
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should show both customer and seller fields
        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 1

        seller_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "seller_contract_id"
        ]
        assert len(seller_blocks) == 1

    def test_build_modal_fn_none_impacts_hides_all_fields(
        self, priority_factory, impact_level_factory
    ):
        """All impacts at NONE level should not show any specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Sellers")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "critical",
            "impact_form_data": {
                "customers_impact": customer_impact,
                "sellers_impact": seller_impact,
            },
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should NOT show any specific fields
        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 0

        seller_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "seller_contract_id"
        ]
        assert len(seller_blocks) == 0

    def test_build_modal_fn_normal_with_customer_shows_team_and_zendesk(
        self, priority_factory, impact_level_factory
    ):
        """P4-P5 with customer impact should show both feature team and Zendesk."""
        priority_factory(value=4, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        modal = OpeningUnifiedModal()

        open_incident_context = {
            "response_type": "normal",
            "impact_form_data": {"customers_impact": customer_impact},
            "details_form_data": {},
        }

        view = modal.build_modal_fn(open_incident_context=open_incident_context)

        # Should show both fields
        team_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "suggested_team_routing"
        ]
        assert len(team_blocks) == 1

        zendesk_blocks = [
            b
            for b in view.blocks
            if hasattr(b, "block_id") and b.block_id == "zendesk_ticket_id"
        ]
        assert len(zendesk_blocks) == 1

    def test_handle_modal_fn_preserves_custom_fields_in_validation(
        self, priority_factory, impact_level_factory
    ):
        """Form validation during submission should preserve custom fields based on impact context."""
        # Setup
        priority = priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        modal = OpeningUnifiedModal()

        # Simulate private_metadata as it would be in the modal submission
        private_metadata = {
            "response_type": "critical",
            "impact_form_data": {"customers_impact": str(customer_impact.id)},
            "details_form_data": {"priority": str(priority.id)},
        }

        # This is what handle_modal_fn now does (with our fix)
        # It passes open_incident_context to the form initialization
        slack_form = modal.get_form_class()(
            data={},  # Empty data for this test - we just want to verify field visibility
            open_incident_context=private_metadata,
        )

        form = slack_form.form

        # Verify that zendesk_ticket_id field exists in the form
        # This proves the context was passed correctly and field visibility was configured
        assert "zendesk_ticket_id" in form.fields, "zendesk_ticket_id should be present in form fields when customer impact is selected"

        # Verify that suggested_team_routing is NOT in the form (critical incident)
        assert "suggested_team_routing" not in form.fields, "suggested_team_routing should not be present for critical incidents"
