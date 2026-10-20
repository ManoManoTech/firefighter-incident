"""Tests for UpdateStatusForm.clean_message status parsing.

The submitted status comes from the raw form data, which is a string for HTML/Slack
submissions but may be an int or an invalid value when the form is fed a plain dict.
"""

from __future__ import annotations

import pytest
from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.update_status import UpdateStatusForm


def _form_with(status: object, message: str) -> UpdateStatusForm:
    incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
    form = UpdateStatusForm(
        data={"status": status, "message": message}, incident=incident
    )
    form.cleaned_data = {"message": message}
    return form


@pytest.mark.django_db
class TestCleanMessageStatusParsing:
    @staticmethod
    def test_int_status_reopening_from_mitigated_needs_justification() -> None:
        form = _form_with(IncidentStatus.INVESTIGATING.value, "short")

        with pytest.raises(forms.ValidationError, match="detailed justification"):
            form.clean_message()

    @staticmethod
    def test_int_status_with_justification_is_accepted() -> None:
        form = _form_with(
            IncidentStatus.MITIGATING.value, "  Root cause came back after deploy  "
        )

        assert form.clean_message() == "Root cause came back after deploy"

    @staticmethod
    def test_invalid_status_value_leaves_validation_to_the_status_field() -> None:
        form = _form_with("not-a-status", "short")

        assert form.clean_message() == "short"

    @staticmethod
    def test_unknown_int_status_leaves_validation_to_the_status_field() -> None:
        form = _form_with(12345, "short")

        assert form.clean_message() == "short"


@pytest.mark.django_db
@pytest.mark.parametrize("status", [IncidentStatus.POST_MORTEM, IncidentStatus.CLOSED])
def test_no_postmortem_workflow_has_no_restriction_after_mitigated(
    status: IncidentStatus,
) -> None:
    """Past MITIGATED, incidents without post-mortem fall back to the default status choices."""
    assert UpdateStatusForm()._get_no_postmortem_allowed_statuses(status) is None
