"""Utilities for modal handling to avoid circular imports."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.slack.views.modals.closure_reason import modal_closure_reason

if TYPE_CHECKING:
    from slack_sdk.models.views import View

    from firefighter.incidents.models.incident import Incident


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


def handle_update_status_close_request(ack: Any, body: dict[str, Any], incident: Incident, target_status: IncidentStatus) -> bool:
    """Handle update status request to close incident, showing reason modal if needed.

    Returns True if the request was handled (reason modal shown), False otherwise.
    """
    if (target_status == IncidentStatus.CLOSED and
        UpdateStatusForm.requires_closure_reason(incident, target_status)):
        # Show closure reason modal instead
        ack(response_action="push", view=modal_closure_reason.build_modal_fn(body, incident))
        return True

    return False
