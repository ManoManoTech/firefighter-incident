"""Tests for unified incident form with conditional field visibility."""
from __future__ import annotations

import pytest
from django import forms

from firefighter.incidents.models.impact import LevelChoices
from firefighter.slack.views.modals.opening.details.unified import (
    UnifiedIncidentFormSlack,
)


@pytest.mark.django_db
class TestUnifiedIncidentFormFieldVisibility:
    """Test that UnifiedIncidentForm shows/hides fields based on impacts and response_type."""

    def test_critical_incident_no_impacts_shows_base_fields_only(self, priority_factory):
        """P1-P3 with no impacts should show only base fields."""
        priority_factory(value=1, default=True)

        form = UnifiedIncidentFormSlack(
            impacts_data={},
            response_type="critical",
        )

        # Base fields always visible
        assert "title" in form.fields
        assert "description" in form.fields
        assert "incident_category" in form.fields
        assert "environment" in form.fields
        assert "platform" in form.fields
        assert "priority" in form.fields

        # Conditional fields should be removed
        assert "suggested_team_routing" not in form.fields
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields
        assert "is_key_account" not in form.fields
        assert "is_seller_in_golden_list" not in form.fields
        assert "zoho_desk_ticket_id" not in form.fields

    def test_normal_incident_shows_feature_team_field(self, priority_factory):
        """P4-P5 should show suggested_team_routing field."""
        priority_factory(value=4, default=True)

        form = UnifiedIncidentFormSlack(
            impacts_data={},
            response_type="normal",
        )

        # Should include feature team field for normal incidents
        assert "suggested_team_routing" in form.fields

        # But not impact-specific fields
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields

    def test_customer_impact_shows_zendesk_field(self, priority_factory, impact_level_factory):
        """Customer impact should show zendesk_ticket_id field."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        impacts_data = {"customers_impact": customer_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include customer-specific fields
        assert "zendesk_ticket_id" in form.fields

        # But not seller fields
        assert "seller_contract_id" not in form.fields
        assert "zoho_desk_ticket_id" not in form.fields

    def test_seller_impact_shows_seller_fields(self, priority_factory, impact_level_factory):
        """Seller impact should show all seller-related fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Sellers")

        impacts_data = {"sellers_impact": seller_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include all seller-specific fields
        assert "seller_contract_id" in form.fields
        assert "is_key_account" in form.fields
        assert "is_seller_in_golden_list" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

        # But not customer fields
        assert "zendesk_ticket_id" not in form.fields

    def test_both_customer_and_seller_impact_shows_all_fields(
        self, priority_factory, impact_level_factory
    ):
        """Both customer and seller impacts should show all related fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        impacts_data = {
            "customers_impact": customer_impact,
            "sellers_impact": seller_impact,
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include both customer and seller fields
        assert "zendesk_ticket_id" in form.fields
        assert "seller_contract_id" in form.fields
        assert "is_key_account" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_none_impact_level_hides_fields(self, priority_factory, impact_level_factory):
        """Impact level NONE should not show impact-specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Customers")

        impacts_data = {"customers_impact": customer_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should NOT include customer fields when impact is NONE
        assert "zendesk_ticket_id" not in form.fields

    def test_employee_impact_shows_no_specific_fields(self, priority_factory, impact_level_factory):
        """Employee impact should not show customer or seller specific fields."""
        priority_factory(value=1, default=True)
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")

        impacts_data = {"employees_impact": employee_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Base fields should be present
        assert "title" in form.fields
        assert "description" in form.fields

        # Should NOT include customer or seller fields
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields
        assert "zoho_desk_ticket_id" not in form.fields

    def test_business_impact_explicit_shows_no_specific_fields(self, priority_factory, impact_level_factory):
        """Business impact should not show customer or seller specific fields."""
        priority_factory(value=1, default=True)
        business_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Business")

        impacts_data = {"business_impact": business_impact}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Base fields should be present
        assert "title" in form.fields

        # Should NOT include customer or seller fields
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields

    def test_customer_and_employee_impact_shows_customer_fields_only(
        self, priority_factory, impact_level_factory
    ):
        """Customer + Employee impact should show customer fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Customers")
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")

        impacts_data = {
            "customers_impact": customer_impact,
            "employees_impact": employee_impact,
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include customer fields
        assert "zendesk_ticket_id" in form.fields

        # But not seller fields
        assert "seller_contract_id" not in form.fields

    def test_seller_and_employee_impact_shows_seller_fields_only(
        self, priority_factory, impact_level_factory
    ):
        """Seller + Employee impact should show seller fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")

        impacts_data = {
            "sellers_impact": seller_impact,
            "employees_impact": employee_impact,
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include seller fields
        assert "seller_contract_id" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

        # But not customer fields
        assert "zendesk_ticket_id" not in form.fields

    def test_all_impacts_shows_all_fields(self, priority_factory, impact_level_factory):
        """All impact types should show all specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")
        business_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Business")

        impacts_data = {
            "customers_impact": customer_impact,
            "sellers_impact": seller_impact,
            "employees_impact": employee_impact,
            "business_impact": business_impact,
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include both customer and seller fields
        assert "zendesk_ticket_id" in form.fields
        assert "seller_contract_id" in form.fields
        assert "is_key_account" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_priority_field_is_hidden_input(self, priority_factory):
        """Priority field should be a hidden input in Slack form."""
        priority_factory(value=1, default=True)

        form = UnifiedIncidentFormSlack(
            impacts_data={},
            response_type="critical",
        )

        # Priority field should exist but be hidden
        assert "priority" in form.fields
        assert isinstance(form.fields["priority"].widget, forms.HiddenInput)


@pytest.mark.django_db
class TestImpactLevelBehavior:
    """Test behavior with different impact levels (SEV, MIN, NONE)."""

    def test_customer_impact_min_shows_zendesk(self, priority_factory, impact_level_factory):
        """Customer impact with MIN level should show Zendesk field."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Customers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"customers_impact": customer_impact},
            response_type="critical",
        )

        assert "zendesk_ticket_id" in form.fields

    def test_customer_impact_sev_shows_zendesk(self, priority_factory, impact_level_factory):
        """Customer impact with SEV level should show Zendesk field."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"customers_impact": customer_impact},
            response_type="critical",
        )

        assert "zendesk_ticket_id" in form.fields

    def test_seller_impact_min_shows_fields(self, priority_factory, impact_level_factory):
        """Seller impact with MIN level should show seller fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"sellers_impact": seller_impact},
            response_type="critical",
        )

        assert "seller_contract_id" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_seller_impact_sev_shows_fields(self, priority_factory, impact_level_factory):
        """Seller impact with SEV level should show seller fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Sellers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"sellers_impact": seller_impact},
            response_type="critical",
        )

        assert "seller_contract_id" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_multiple_none_impacts_hides_all_fields(self, priority_factory, impact_level_factory):
        """All impacts at NONE level should not show any specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Sellers")

        form = UnifiedIncidentFormSlack(
            impacts_data={
                "customers_impact": customer_impact,
                "sellers_impact": seller_impact,
            },
            response_type="critical",
        )

        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields


@pytest.mark.django_db
class TestNormalIncidentBehavior:
    """Test P4-P5 normal incident specific behavior."""

    def test_normal_incident_with_customer_impact_shows_both_team_and_zendesk(
        self, priority_factory, impact_level_factory
    ):
        """P4-P5 with customer impact should show both feature team and Zendesk."""
        priority_factory(value=4, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"customers_impact": customer_impact},
            response_type="normal",
        )

        # Should show both P4-P5 field and customer field
        assert "suggested_team_routing" in form.fields
        assert "zendesk_ticket_id" in form.fields

    def test_normal_incident_with_seller_impact_shows_both_team_and_seller_fields(
        self, priority_factory, impact_level_factory
    ):
        """P4-P5 with seller impact should show both feature team and seller fields."""
        priority_factory(value=5, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        form = UnifiedIncidentFormSlack(
            impacts_data={"sellers_impact": seller_impact},
            response_type="normal",
        )

        # Should show both P4-P5 field and seller fields
        assert "suggested_team_routing" in form.fields
        assert "seller_contract_id" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_normal_incident_employee_only_shows_team_field_only(
        self, priority_factory, impact_level_factory
    ):
        """P4-P5 with only employee impact should show only feature team."""
        priority_factory(value=4, default=True)
        employee_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Employees")

        form = UnifiedIncidentFormSlack(
            impacts_data={"employees_impact": employee_impact},
            response_type="normal",
        )

        # Should only show P4-P5 field
        assert "suggested_team_routing" in form.fields

        # But not customer or seller fields
        assert "zendesk_ticket_id" not in form.fields
        assert "seller_contract_id" not in form.fields


@pytest.mark.django_db
class TestUnifiedIncidentFormValidation:
    """Test form validation with conditional requirements."""

    def test_suggested_team_routing_required_for_normal_incidents(
        self, priority_factory
    ):
        """Feature Team should be required for P4-P5 incidents."""
        priority_factory(value=4, default=True)

        form = UnifiedIncidentFormSlack(
            data={},
            initial={"response_type": "normal"},
            impacts_data={},
            response_type="normal",
        )

        # Should be invalid because suggested_team_routing is required
        assert not form.is_valid()
        assert "suggested_team_routing" in form.errors


@pytest.mark.django_db
class TestGetVisibleFieldsForImpacts:
    """Test the get_visible_fields_for_impacts method."""

    def test_returns_base_fields_for_empty_impacts(self, priority_factory):
        """Should return base fields when no impacts."""
        priority_factory(value=1, default=True)
        form = UnifiedIncidentFormSlack()

        visible = form.get_visible_fields_for_impacts({}, "critical")

        assert "title" in visible
        assert "description" in visible
        assert "incident_category" in visible
        assert "environment" in visible
        assert "platform" in visible
        assert "priority" in visible

        # Should not include conditional fields
        assert "suggested_team_routing" not in visible
        assert "zendesk_ticket_id" not in visible

    def test_includes_feature_team_for_normal_response(self, priority_factory):
        """Should include suggested_team_routing for normal incidents."""
        priority_factory(value=4, default=True)
        form = UnifiedIncidentFormSlack()

        visible = form.get_visible_fields_for_impacts({}, "normal")

        assert "suggested_team_routing" in visible


@pytest.mark.django_db
class TestGetVisibleFieldsForImpactsWithUUIDs:
    """Test the get_visible_fields_for_impacts method with UUID strings (Slack use case)."""

    def test_customer_impact_uuid_shows_zendesk_field(self, priority_factory, impact_level_factory):
        """Customer impact UUID should show zendesk_ticket_id field."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")

        # Pass UUID string instead of object (simulates Slack form submission)
        impacts_data = {"set_impact_type_customers_impact": str(customer_impact.id)}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include customer-specific fields
        assert "zendesk_ticket_id" in form.fields

        # But not seller fields
        assert "seller_contract_id" not in form.fields
        assert "zoho_desk_ticket_id" not in form.fields

    def test_seller_impact_uuid_shows_seller_fields(self, priority_factory, impact_level_factory):
        """Seller impact UUID should show all seller-related fields."""
        priority_factory(value=1, default=True)
        seller_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Sellers")

        # Pass UUID string instead of object
        impacts_data = {"set_impact_type_sellers_impact": str(seller_impact.id)}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include all seller-specific fields
        assert "seller_contract_id" in form.fields
        assert "is_key_account" in form.fields
        assert "is_seller_in_golden_list" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

        # But not customer fields
        assert "zendesk_ticket_id" not in form.fields

    def test_none_impact_uuid_hides_fields(self, priority_factory, impact_level_factory):
        """Impact level NONE UUID should not show impact-specific fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.NONE, impact__name="Customers")

        # Pass UUID string for NONE impact
        impacts_data = {"set_impact_type_customers_impact": str(customer_impact.id)}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should NOT include customer fields when impact is NONE
        assert "zendesk_ticket_id" not in form.fields

    def test_both_customer_and_seller_impact_uuids_show_all_fields(
        self, priority_factory, impact_level_factory
    ):
        """Both customer and seller impact UUIDs should show all related fields."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        # Pass UUID strings for both impacts
        impacts_data = {
            "set_impact_type_customers_impact": str(customer_impact.id),
            "set_impact_type_sellers_impact": str(seller_impact.id),
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should include both customer and seller fields
        assert "zendesk_ticket_id" in form.fields
        assert "seller_contract_id" in form.fields
        assert "is_key_account" in form.fields
        assert "zoho_desk_ticket_id" in form.fields

    def test_invalid_uuid_hides_fields(self, priority_factory):
        """Invalid/non-existent UUID should not show impact-specific fields."""
        priority_factory(value=1, default=True)

        # Pass invalid UUID
        impacts_data = {"set_impact_type_customers_impact": "00000000-0000-0000-0000-000000000000"}

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should NOT include customer fields for invalid UUID
        assert "zendesk_ticket_id" not in form.fields

    def test_mixed_objects_and_uuids(self, priority_factory, impact_level_factory):
        """Should handle mix of ImpactLevel objects and UUID strings."""
        priority_factory(value=1, default=True)
        customer_impact = impact_level_factory(value=LevelChoices.HIGH, impact__name="Customers")
        seller_impact = impact_level_factory(value=LevelChoices.LOW, impact__name="Sellers")

        # Mix object and UUID string
        impacts_data = {
            "customers_impact": customer_impact,  # Object
            "set_impact_type_sellers_impact": str(seller_impact.id),  # UUID string
        }

        form = UnifiedIncidentFormSlack(
            impacts_data=impacts_data,
            response_type="critical",
        )

        # Should handle both types correctly
        assert "zendesk_ticket_id" in form.fields
        assert "seller_contract_id" in form.fields
