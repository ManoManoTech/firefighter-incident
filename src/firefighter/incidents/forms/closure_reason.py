"""Form for incident closure with reason when closing from early statuses."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.enums import ClosureReason

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident


class IncidentClosureReasonForm(forms.Form):
    """Form for closing an incident with a mandatory reason from early statuses."""

    closure_reason = forms.ChoiceField(
        label="Closure Reason",
        choices=ClosureReason.choices,
        required=True,
        help_text="Select the reason for closing this incident",
    )
    closure_reference = forms.CharField(
        label="Reference (optional)",
        max_length=100,
        required=False,
        help_text="Reference incident ID or external link for context (e.g., #1234 or URL)",
    )
    message = forms.CharField(
        label="Closure Message",
        widget=forms.Textarea,
        required=True,
        help_text="Brief explanation of why this incident is being closed",
    )

    def __init__(self, *args: Any, incident: Incident | None = None, **kwargs: Any) -> None:  # noqa: ARG002
        super().__init__(*args, **kwargs)

        # Exclude RESOLVED from choices as it's for normal workflow closure
        closure_field = self.fields["closure_reason"]
        if hasattr(closure_field, "choices"):
            closure_field.choices = [
                choice for choice in ClosureReason.choices
                if choice[0] != ClosureReason.RESOLVED
            ]
