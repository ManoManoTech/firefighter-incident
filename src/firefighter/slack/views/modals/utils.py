"""Utilities for modal handling to avoid circular imports."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.slack.views.modals.closure_reason import modal_closure_reason

if TYPE_CHECKING:
    from django.forms import Form
    from slack_sdk.models.views import View

    from firefighter.incidents.models.incident import Incident


# Fields from the Update Status form that can be carried over to the closure
# reason modal so changes are not lost when Slack pushes the second modal.
_CARRY_OVER_FK_FIELDS: tuple[str, ...] = ("priority", "incident_category")


def get_close_modal_view(body: dict[str, Any], incident: Incident, **kwargs: Any) -> View | None:
    """Get the appropriate modal view for closing an incident.

    This function determines whether to show the closure reason modal
    or delegate to the normal close modal.
    """
    # Check if closure reason is required
    if UpdateStatusForm.requires_closure_reason(incident, IncidentStatus.CLOSED):
        return modal_closure_reason.build_modal_fn(body, incident, **kwargs)

    # Return None to indicate normal close modal should be used
    return None


def handle_close_modal_callback(ack: Any, body: dict[str, Any], incident: Incident, user: Any) -> bool | None:
    """Handle modal callback, delegating to closure reason modal if needed."""
    # Check if this is a closure reason modal callback
    if body.get("view", {}).get("callback_id") == "incident_closure_reason":
        return modal_closure_reason.handle_modal_fn(ack, body, incident, user)

    # Return None to indicate normal handling should continue
    return None


def handle_update_status_close_request(
    ack: Any,
    body: dict[str, Any],
    incident: Incident,
    target_status: IncidentStatus,
    form: Form | None = None,
) -> bool:
    """Handle update status request to close incident, showing reason modal if needed.

    When the closure reason modal is pushed on top of the Update Status modal,
    the Update Status submission is dropped by Slack. Any fields that were
    changed alongside the status (priority, incident_category, ...) would be
    silently lost. To avoid that, we collect those changes from the form and
    pass them as carry-over data so the closure reason modal can re-apply them
    on submission.

    Returns True if the request was handled (reason modal shown), False otherwise.
    """
    if (target_status == IncidentStatus.CLOSED and
        UpdateStatusForm.requires_closure_reason(incident, target_status)):
        carry_over = _build_carry_over_from_form(form)
        ack(
            response_action="push",
            view=modal_closure_reason.build_modal_fn(
                body, incident, carry_over=carry_over
            ),
        )
        return True

    return False


def _build_carry_over_from_form(form: Form | None) -> dict[str, Any]:
    """Collect carry-over fields from the Update Status form's changed data."""
    if form is None:
        return {}
    carry_over: dict[str, Any] = {}
    changed = set(getattr(form, "changed_data", []) or [])
    cleaned = getattr(form, "cleaned_data", {}) or {}
    for field in _CARRY_OVER_FK_FIELDS:
        if field in changed and cleaned.get(field) is not None:
            carry_over[f"{field}_id"] = str(cleaned[field].id)
    return carry_over
