from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.utils import EnumChoiceField, GroupedModelChoiceField
from firefighter.incidents.models import IncidentCategory, Priority

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident


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

    def __init__(self, *args: Any, incident: Incident | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Dynamically adjust status choices based on incident requirements
        if incident:
            current_status = incident.status

            # Check if incident requires post-mortem (P1/P2 in PRD)
            # We check the conditions directly rather than using incident.needs_postmortem
            # because that property also checks if confluence is installed
            requires_postmortem = (
                incident.priority
                and incident.environment
                and incident.priority.needs_postmortem
                and incident.environment.value == "PRD"
            )

            # Get the status field (we know it's an EnumChoiceField)
            status_field = self.fields["status"]

            # For incidents requiring post-mortem (P1/P2 in PRD)
            if requires_postmortem:
                if current_status == IncidentStatus.OPEN:
                    # From Opened: can go to INVESTIGATING or CLOSED (with reason)
                    allowed_statuses = [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]
                    status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
                elif current_status == IncidentStatus.INVESTIGATING:
                    # From Investigating: can go to MITIGATING or CLOSED (with reason)
                    allowed_statuses = [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]
                    status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
                elif current_status == IncidentStatus.MITIGATING:
                    # From Mitigating: can only go to MITIGATED
                    allowed_statuses = [IncidentStatus.MITIGATED]
                    status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
                elif current_status == IncidentStatus.MITIGATED:
                    # From Mitigated: can only go to POST_MORTEM
                    allowed_statuses = [IncidentStatus.POST_MORTEM]
                    status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
                elif current_status == IncidentStatus.POST_MORTEM:
                    # From Post-mortem: can only go to CLOSED
                    allowed_statuses = [IncidentStatus.CLOSED]
                    status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
                else:
                    # Default: all statuses up to closed
                    status_field.choices = IncidentStatus.choices_lte(IncidentStatus.CLOSED)  # type: ignore[attr-defined]
            # For P3+ incidents (no post-mortem needed)
            elif current_status == IncidentStatus.OPEN:
                # From Opened: can go to INVESTIGATING or CLOSED (with reason)
                allowed_statuses = [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]
                status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
            elif current_status == IncidentStatus.INVESTIGATING:
                # From Investigating: can go to MITIGATING or CLOSED (with reason)
                allowed_statuses = [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]
                status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
            elif current_status == IncidentStatus.MITIGATING:
                # From Mitigating: can only go to MITIGATED
                allowed_statuses = [IncidentStatus.MITIGATED]
                status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
            elif current_status == IncidentStatus.MITIGATED:
                # From Mitigated: can go to CLOSED (P3+ doesn't need post-mortem)
                allowed_statuses = [IncidentStatus.CLOSED]
                status_field.choices = [(s.value, s.label) for s in allowed_statuses]  # type: ignore[attr-defined]
            else:
                # Default fallback
                status_field.choices = IncidentStatus.choices_lte_skip_postmortem(IncidentStatus.CLOSED)  # type: ignore[attr-defined]

    @staticmethod
    def requires_closure_reason(incident: Incident, target_status: IncidentStatus) -> bool:
        """Check if closing this incident to the target status requires a closure reason.

        Based on the workflow diagram:
        - P1/P2 and P3/P4/P5: require reason when closing from Opened or Investigating
        """
        if target_status != IncidentStatus.CLOSED:
            return False

        current_status = incident.status

        # Require reason if closing from Opened or Investigating (for any priority)
        return current_status.value in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}
