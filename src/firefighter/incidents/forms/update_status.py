from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.utils import EnumChoiceField, GroupedModelChoiceField
from firefighter.incidents.models import IncidentCategory, Priority

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident

logger = logging.getLogger(__name__)


class UpdateStatusForm(forms.Form):
    message = forms.CharField(
        label="Update message",
        widget=forms.Textarea,
        min_length=10,
        max_length=1200,
        required=False,
    )
    status = EnumChoiceField(
        enum_class=IncidentStatus,
        label="Status",
        choices=IncidentStatus.choices_lte(IncidentStatus.CLOSED),
    )
    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_update=True),
    )
    incident_category = GroupedModelChoiceField(
        choices_groupby="group",
        label="Incident category",
        queryset=IncidentCategory.objects.all()
        .select_related("group")
        .order_by(
            "group__order",
            "name",
        ),
    )

    def __init__(
        self, *args: Any, incident: Incident | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)

        # Store incident for later use in clean()
        self.incident = incident

        # Dynamically adjust status choices based on incident requirements
        if incident:
            self._set_status_choices(incident)

    def _set_status_choices(self, incident: Incident) -> None:
        """Set the status field choices based on the incident's current state and requirements."""
        current_status = incident.status
        status_field = self.fields["status"]

        # Check if incident requires post-mortem (P1/P2 in PRD)
        requires_postmortem = bool(
            incident.priority
            and incident.environment
            and incident.priority.needs_postmortem
            and incident.environment.value == "PRD"
        )
        allowed_statuses = self._get_allowed_statuses(
            current_status, requires_postmortem=requires_postmortem
        )

        # If we got a list of enum values, convert to choices and include current status
        if allowed_statuses:
            if current_status not in allowed_statuses:
                allowed_statuses.insert(0, current_status)
            # Convert values to strings to match what Slack sends in form submissions
            choices = [(str(s.value), s.label) for s in allowed_statuses]
            status_field.choices = choices  # type: ignore[attr-defined]

    def _get_allowed_statuses(
        self, current_status: IncidentStatus, *, requires_postmortem: bool
    ) -> list[IncidentStatus] | None:
        """Get allowed status transitions based on current status and postmortem requirement.

        Returns None if choices should be set directly (for default fallback cases).
        """
        # For incidents requiring post-mortem (P1/P2 in PRD)
        if requires_postmortem:
            return self._get_postmortem_allowed_statuses(current_status)

        # For P3+ incidents (no post-mortem needed)
        return self._get_no_postmortem_allowed_statuses(current_status)

    def _get_postmortem_allowed_statuses(
        self, current_status: IncidentStatus
    ) -> list[IncidentStatus] | None:
        """Get allowed statuses for incidents requiring postmortem (P1/P2)."""
        if current_status == IncidentStatus.OPEN:
            return [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]
        if current_status == IncidentStatus.INVESTIGATING:
            return [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]
        if current_status == IncidentStatus.MITIGATING:
            return [IncidentStatus.MITIGATED]
        if current_status == IncidentStatus.MITIGATED:
            # P1/P2 can: go to POST_MORTEM (required) OR reopen to INVESTIGATING/MITIGATING (with reason)
            return [
                IncidentStatus.POST_MORTEM,      # Required next step
                IncidentStatus.INVESTIGATING,   # Reopen option (with reason)
                IncidentStatus.MITIGATING,      # Reopen option (with reason)
            ]
        if current_status == IncidentStatus.POST_MORTEM:
            return [IncidentStatus.CLOSED]

        # For any other status, return None to use the default choices
        return None

    def _get_no_postmortem_allowed_statuses(
        self, current_status: IncidentStatus
    ) -> list[IncidentStatus] | None:
        """Get allowed statuses for incidents not requiring postmortem (P3/P4/P5)."""
        if current_status == IncidentStatus.OPEN:
            return [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]
        if current_status == IncidentStatus.INVESTIGATING:
            return [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]
        if current_status == IncidentStatus.MITIGATING:
            return [IncidentStatus.MITIGATED]
        if current_status == IncidentStatus.MITIGATED:
            # P3/P4/P5 can: go to CLOSED (normal next step) OR reopen to INVESTIGATING/MITIGATING (with reason)
            return [
                IncidentStatus.CLOSED,          # Normal next step for P3+
                IncidentStatus.INVESTIGATING,   # Reopen option (with reason)
                IncidentStatus.MITIGATING,      # Reopen option (with reason)
            ]

        # For any other status, return None to use the default choices
        return None

    def _set_default_choices(
        self, status_field: Any, current_status: IncidentStatus, default_choices: Any
    ) -> None:
        """Set status field choices to default, ensuring current status is included."""
        # Convert default_choices to string keys to match Slack form submissions
        status_field.choices = [
            (str(choice[0]), choice[1]) for choice in default_choices
        ]
        existing_values = {choice[0] for choice in status_field.choices}
        if str(current_status.value) not in existing_values:
            # Insert current status at the beginning
            status_field.choices = [
                (str(current_status.value), current_status.label),
                *status_field.choices,
            ]

    @staticmethod
    def requires_closure_reason(
        incident: Incident, target_status: IncidentStatus
    ) -> bool:
        """Check if closing this incident to the target status requires a closure reason.

        Based on the workflow diagram:
        - P1/P2 and P3/P4/P5: require reason when closing from Opened or Investigating
        """
        if target_status != IncidentStatus.CLOSED:
            return False

        current_status = incident.status

        # Require reason if closing from Opened or Investigating (for any priority)
        return current_status.value in {
            IncidentStatus.OPEN,
            IncidentStatus.INVESTIGATING,
        }

    def clean_message(self) -> str:
        """Validate message field, ensuring reopening from MITIGATED has sufficient justification."""
        message = self.cleaned_data.get("message", "").strip()

        # Get the incident and status from form data/initialization
        incident = getattr(self, "incident", None)
        status_value = self.data.get("status")  # Use raw form data as cleaned_data may not be ready yet

        if incident and status_value:
            current_status = incident.status

            # Convert status value to enum if it's a string/number
            try:
                if isinstance(status_value, str):
                    status = IncidentStatus(int(status_value))
                else:
                    status = IncidentStatus(status_value)
            except (ValueError, TypeError):
                # Invalid status value, let other validation handle it
                return message

            # If reopening from MITIGATED to earlier phases, require substantial justification
            if (current_status == IncidentStatus.MITIGATED and
                status in {IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATING} and
                len(message) < 10):
                raise forms.ValidationError(
                    "A detailed justification (minimum 10 characters) is required when reopening "
                    "an incident from MITIGATED status."
                )

        return message
