from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident_update import IncidentUpdate

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import datetime

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

# (event_type, display label) - mirrors review_timeline._MILESTONE_EVENT_TYPES.
_MILESTONE_EVENT_TYPES: tuple[tuple[str, str], ...] = (
    ("started", "Started"),
    ("detected", "Detected"),
)


class TimelineCorrectionForm(forms.Form):
    """Edit in place the timeline shown in the Post-mortem review checkpoint.

    Two kinds of fields, both keyed to survive round-tripping through Slack's
    view submission parsing (which strips block/action ids at the first
    "___" - see `slack_view_submission_to_dict`):

    - `milestone_<event_type>`: same update_or_create/delete semantics as
      `IncidentUpdateKeyEventsForm._save_key_event` - these rows aren't
      unique per status, so "which one to touch" is never ambiguous.
    - `status_<incident_update_id>`: edits that exact `IncidentUpdate` row's
      `event_ts` in place - required, since a status transition that
      happened must keep some time. `IncidentStatus.OPEN` has no field, even
      for a genuine reopen back to OPEN: the declaration's OPEN is always
      anchored to `incident.created_at` rather than a recorded row, and a
      later reopen-to-OPEN is deliberately left non-editable here too, to
      keep the rule simple ("OPEN is never a correction target"). A status
      revisited after a reopen
      (MITIGATED -> INVESTIGATING/MITIGATING) gets one field per occurrence,
      matching `get_status_timeline`'s full history and the Jira post-mortem
      timeline - labels are numbered ("Mitigating (1)", "Mitigating (2)")
      only when a status actually recurs.
    """

    incident: Incident
    user: User

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.incident = kwargs.pop("incident")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.generate_fields_dynamically()

    def generate_fields_dynamically(self) -> None:
        milestone_updates = dict(
            self.incident.incidentupdate_set.filter(
                event_type__in=[
                    event_type for event_type, _ in _MILESTONE_EVENT_TYPES
                ]
            ).values_list("event_type", "event_ts")
        )
        for event_type, label in _MILESTONE_EVENT_TYPES:
            field_name = f"milestone_{event_type}"
            self.fields[field_name] = forms.DateTimeField(
                required=False,
                # Slack itself appends "(optional)" next to the label for any
                # non-required field (see form_utils.py's optional=not
                # f.required) - adding it here too would show it twice.
                label=label,
                widget=forms.DateTimeInput(
                    attrs={"placeholder": event_type, "type": "datetime-local"}
                ),
            )
            if field_name not in self.initial:
                self.initial[field_name] = milestone_updates.get(event_type) or ""

        for status, occurrence, total, update in self._status_updates_with_occurrence():
            field_name = f"status_{update.id}"
            label = status.label if total == 1 else f"{status.label} ({occurrence})"
            self.fields[field_name] = forms.DateTimeField(
                required=True,
                label=label,
                widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
            )
            if field_name not in self.initial:
                self.initial[field_name] = update.event_ts

    def _status_updates_with_occurrence(
        self,
    ) -> list[tuple[IncidentStatus, int, int, IncidentUpdate]]:
        """Every non-OPEN status-change row, in chronological order.

        Yields `(status, occurrence_index, occurrence_total, update)` so a
        status reached more than once (reopen cycles) can be numbered
        ("Mitigating (1)", "Mitigating (2)") while a status reached only
        once keeps a bare label. Mirrors `review_timeline.get_status_timeline`
        - full history, no dedup - minus the OPEN special-case (OPEN, including
        a later reopen back to OPEN, is never an editable row here).
        """
        updates = list(
            self.incident.incidentupdate_set.filter(_status__isnull=False)
            .exclude(_status=IncidentStatus.OPEN)
            .order_by("event_ts")
        )
        totals: dict[IncidentStatus, int] = {}
        for update in updates:
            if update.status is not None:
                totals[update.status] = totals.get(update.status, 0) + 1

        seen: dict[IncidentStatus, int] = {}
        result: list[tuple[IncidentStatus, int, int, IncidentUpdate]] = []
        for update in updates:
            status = update.status
            if status is None:
                continue
            seen[status] = seen.get(status, 0) + 1
            result.append((status, seen[status], totals[status], update))
        return result

    def clean(self) -> dict[str, Any] | None:
        if self.user is None:
            raise forms.ValidationError("User is required")
        return super().clean()

    def save(self) -> None:
        """Save each changed field in place."""
        for field_name in self.changed_data:
            value = self.cleaned_data[field_name]
            if field_name.startswith("milestone_"):
                self._save_milestone(field_name.removeprefix("milestone_"), value)
            elif field_name.startswith("status_"):
                self._save_status(field_name.removeprefix("status_"), value)

    def _save_milestone(self, event_type: str, value: datetime | None) -> None:
        if value is None:
            IncidentUpdate.objects.filter(
                incident_id=self.incident.id, event_type=event_type
            ).delete()
            return
        IncidentUpdate.objects.update_or_create(
            incident_id=self.incident.id,
            event_type=event_type,
            defaults={"event_ts": value, "created_by": self.user},
        )

    @staticmethod
    def _save_status(update_id: str, value: datetime) -> None:
        IncidentUpdate.objects.filter(id=update_id).update(event_ts=value)
