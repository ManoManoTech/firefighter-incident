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


# Which occurrence of a status is the definitive one when a reopen makes it
# repeat: investigation *started* at its first occurrence, while the mitigation
# that actually held is the last one. Shared with the Slack review message so
# both surfaces show and edit the same timestamp.
DEFINITIVE_OCCURRENCE: dict[IncidentStatus, str] = {
    IncidentStatus.INVESTIGATING: "first",
    IncidentStatus.MITIGATING: "last",
    IncidentStatus.MITIGATED: "last",
}
_DEFAULT_OCCURRENCE = "last"


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
            )
            # Explicit ordering: without it Meta.ordering ("-event_ts") applies and
            # dict() would keep the OLDEST row per type, while the review message
            # keeps the newest - the two surfaces would disagree on the same field.
            .order_by("event_ts")
            .values_list("event_type", "event_ts")
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

        for status, total, update in self._editable_status_updates():
            field_name = f"status_{update.id}"
            which = DEFINITIVE_OCCURRENCE.get(status, _DEFAULT_OCCURRENCE)
            label = (
                status.label
                if total == 1
                else f"{status.label} ({which} of {total})"
            )
            self.fields[field_name] = forms.DateTimeField(
                required=True,
                label=label,
                widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
            )
            if field_name not in self.initial:
                self.initial[field_name] = update.event_ts

    def _editable_status_updates(
        self,
    ) -> list[tuple[IncidentStatus, int, IncidentUpdate]]:
        """One editable row per non-OPEN status, in chronological order.

        A status reached several times (reopen cycles) yields a single field
        bound to its *last* occurrence: that is the time the incident actually
        settled on, the one the post-mortem timeline shows, and the only one
        worth correcting. Earlier occurrences stay as recorded - they are the
        history of the failed attempts, not a mistake to fix.

        Returns `(status, occurrence_count, update)`; the count is surfaced in
        the label ("Mitigated (last of 4)") rather than as one numbered field
        per cycle. OPEN is never editable here, including a later reopen to OPEN.
        """
        updates = list(
            self.incident.incidentupdate_set.filter(_status__isnull=False)
            .exclude(_status=IncidentStatus.OPEN)
            .order_by("event_ts")
        )
        totals: dict[IncidentStatus, int] = {}
        chosen: dict[IncidentStatus, IncidentUpdate] = {}
        for update in updates:
            status = update.status
            if status is None:
                continue
            totals[status] = totals.get(status, 0) + 1
            which = DEFINITIVE_OCCURRENCE.get(status, _DEFAULT_OCCURRENCE)
            if which == "last" or status not in chosen:
                chosen[status] = update

        return [
            (status, totals[status], update)
            for status, update in sorted(
                chosen.items(), key=lambda item: item[1].event_ts
            )
        ]

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
