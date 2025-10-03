"""Test the closure reason form."""
from __future__ import annotations

import pytest
from django.test import TestCase

from firefighter.incidents.enums import ClosureReason
from firefighter.incidents.forms.closure_reason import IncidentClosureReasonForm


@pytest.mark.django_db
class TestIncidentClosureReasonForm(TestCase):
    """Test the IncidentClosureReasonForm."""

    def test_form_initialization(self):
        """Test that the form initializes correctly."""
        form = IncidentClosureReasonForm()

        # Check that all required fields are present
        assert "closure_reason" in form.fields
        assert "closure_reference" in form.fields
        assert "message" in form.fields

    def test_closure_reason_field_choices(self):
        """Test that closure reason field has correct choices."""
        form = IncidentClosureReasonForm()
        closure_reason_field = form.fields["closure_reason"]

        # Check that closure reasons are available (except RESOLVED which is excluded)
        choices = dict(closure_reason_field.choices)
        assert "resolved" not in choices  # RESOLVED is excluded
        assert "duplicate" in choices
        assert "false_positive" in choices
        assert "superseded" in choices
        assert "external" in choices
        assert "cancelled" in choices

    def test_valid_form_submission(self):
        """Test form with valid data."""
        data = {
            "closure_reason": ClosureReason.DUPLICATE,  # Use a valid choice (not RESOLVED)
            "closure_reference": "Fixed by restarting service",
            "message": "The incident has been resolved by restarting the affected service."
        }
        form = IncidentClosureReasonForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_with_minimal_data(self):
        """Test form with minimal required data."""
        data = {
            "closure_reason": ClosureReason.DUPLICATE,
            "message": "Duplicate of incident #123"
        }
        form = IncidentClosureReasonForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_missing_closure_reason(self):
        """Test form validation when closure_reason is missing."""
        data = {
            "message": "Test message"
        }
        form = IncidentClosureReasonForm(data=data)
        assert not form.is_valid()
        assert "closure_reason" in form.errors

    def test_form_missing_message(self):
        """Test form validation when message is missing."""
        data = {
            "closure_reason": ClosureReason.DUPLICATE
        }
        form = IncidentClosureReasonForm(data=data)
        assert not form.is_valid()
        assert "message" in form.errors

    def test_message_field_constraints(self):
        """Test message field length constraints."""
        # Test valid message (no length constraints defined in the form)
        data = {
            "closure_reason": ClosureReason.DUPLICATE,
            "message": "This is a valid message that meets the requirements."
        }
        form = IncidentClosureReasonForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_excludes_resolved_reason(self):
        """Test that RESOLVED is excluded from choices."""
        form = IncidentClosureReasonForm()
        choices = dict(form.fields["closure_reason"].choices)

        # RESOLVED should be excluded for early closure forms
        assert "resolved" not in choices
