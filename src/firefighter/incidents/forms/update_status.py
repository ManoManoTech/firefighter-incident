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
        logger.debug(f"DEBUG: incident.priority={incident.priority}")
        logger.debug(f"DEBUG: incident.environment={incident.environment}")
        if incident.priority:
            logger.debug(f"DEBUG: incident.priority.needs_postmortem={incident.priority.needs_postmortem}")
            logger.debug(f"DEBUG: incident.priority.value={incident.priority.value}")
        if incident.environment:
            logger.debug(f"DEBUG: incident.environment.value={incident.environment.value}")
        requires_postmortem = bool(
            incident.priority
            and incident.environment
            and incident.priority.needs_postmortem
            and incident.environment.value == "PRD"
        )
        logger.debug(f"DEBUG PRINT: About to call _get_allowed_statuses with current_status={current_status}, requires_postmortem={requires_postmortem}")
        allowed_statuses = self._get_allowed_statuses(
            current_status, requires_postmortem=requires_postmortem
        )
        
        logger.debug(f"DEBUG PRINT: _get_allowed_statuses returned {allowed_statuses} for current_status={current_status}, requires_postmortem={requires_postmortem}")
        logger.debug(
            f"DEBUG: _get_allowed_statuses returned {allowed_statuses} for "
            f"current_status={current_status}, requires_postmortem={requires_postmortem}"
        )

        # If we got a list of enum values, convert to choices and include current status
        if allowed_statuses:
            if current_status not in allowed_statuses:
                allowed_statuses.insert(0, current_status)
            # Convert values to strings to match what Slack sends in form submissions
            choices = [(str(s.value), s.label) for s in allowed_statuses]
            status_field.choices = choices  # type: ignore[attr-defined]
            logger.debug(
                f"Set status choices for incident #{incident.id}: {choices} "
                f"(current_status={current_status}, requires_postmortem={requires_postmortem})"
            )
        else:
            logger.debug(
                f"No allowed_statuses returned, keeping default choices for incident #{incident.id}"
            )

    def _get_allowed_statuses(
        self, current_status: IncidentStatus, *, requires_postmortem: bool
    ) -> list[IncidentStatus] | None:
        """Get allowed status transitions based on current status and postmortem requirement.

        Returns None if choices should be set directly (for default fallback cases).
        """
        status_field = self.fields["status"]

        # For incidents requiring post-mortem (P1/P2 in PRD)
        if requires_postmortem:
            return self._get_postmortem_allowed_statuses(current_status, status_field)

        # For P3+ incidents (no post-mortem needed)
        return self._get_no_postmortem_allowed_statuses(current_status, status_field)

    def _get_postmortem_allowed_statuses(
        self, current_status: IncidentStatus, status_field: Any
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
        self, current_status: IncidentStatus, status_field: Any
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
        print(f"DEBUG: _get_no_postmortem_allowed_statuses returning None for status {current_status}")
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

    @staticmethod
    def requires_reopening_reason(
        incident: Incident, target_status: IncidentStatus
    ) -> bool:
        """Check if reopening this incident from MITIGATED requires a reason.

        Require justification when going back from MITIGATED to previous states.
        """
        if incident.status != IncidentStatus.MITIGATED:
            return False

        # Require reason if returning from MITIGATED to previous states
        return target_status.value in {
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
        }

    def clean(self) -> dict[str, Any]:
        """Validate the form data, especially message requirements."""
        cleaned_data = super().clean()

        # Check if we need a message for reopening from MITIGATED
        if self.incident:
            status = cleaned_data.get("status")
            if status and isinstance(status, IncidentStatus):
                if self.requires_reopening_reason(self.incident, status):
                    message = cleaned_data.get("message", "").strip()
                    if not message:
                        raise forms.ValidationError(
                            {
                                "message": "A justification message is required when reopening an incident from Mitigated status."
                            }
                        )
                    if len(message) < 10:
                        raise forms.ValidationError(
                            {
                                "message": "Justification message must be at least 10 characters when reopening from Mitigated status."
                            }
                        )

        return cleaned_data
