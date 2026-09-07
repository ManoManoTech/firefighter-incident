"""One editable form for the whole incident timeline, shared by both Slack surfaces.

Milestones (Key Events) and status timestamps used to be edited in two different
places, with two different field sets: the Key Events message could not touch
Investigating/Mitigating/Mitigated, and the correction message only offered the
statuses the incident had actually been through - so a step that was never
recorded could not be filled in at all. Both surfaces now render this form, which
covers every key event that can be corrected, whether or not it was recorded.

The two surfaces keep their own action ids through `field_prefix`, so a field
edited in one message routes back to that message and not to the other.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from django import forms

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.milestone_type import MilestoneType
from firefighter.incidents.timeline import (
    DEFAULT_OCCURRENCE,
    DEFINITIVE_OCCURRENCE,
    EXPECTED_STEPS,
    milestone_timestamps,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import datetime

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

# The step the sequence ends on. Editable milestones that are not part of the
# seven canonical steps (Recovered, in the default fixtures) are rendered just
# before it: Post-mortem is the administrative step that closes the timeline, so
# anything else recorded about the incident belongs ahead of it.
_LAST_STEP_STATUS = IncidentStatus.POST_MORTEM

# Statuses shown in the timeline but never offered as a field:
# - OPEN is the declaration, anchored to `incident.created_at`, and a later
#   reopen to OPEN is history rather than a mistake to fix.
# - POST_MORTEM is stamped by the transition itself, at the instant it happens -
#   and that transition is exactly what the review checkpoint gates. There is
#   nothing to correct about it after the fact.
_NON_EDITABLE_STATUSES = frozenset({IncidentStatus.OPEN, IncidentStatus.POST_MORTEM})


class _FieldSpec(NamedTuple):
    name: str
    label: str
    initial: datetime | None
    required: bool


class IncidentTimelineForm(forms.Form):
    """Every correctable key event of an incident, in canonical order.

    Two kinds of fields, both keyed to survive round-tripping through Slack's
    view submission parsing (which strips block/action ids at the first
    "___" - see `slack_view_submission_to_dict`):

    - `milestone_<event_type>`: same update_or_create/delete semantics as
      `IncidentUpdateKeyEventsForm._save_key_event` - these rows aren't unique
      per status, so "which one to touch" is never ambiguous. Only milestones
      flagged `user_editable` are offered; `Declared` is not one of them, since
      it is the incident's declaration time.
    - `status_<status value>`: the timestamp of that status. When the incident
      went through it, the definitive occurrence is edited in place - the one
      the post-mortem timeline shows (`DEFINITIVE_OCCURRENCE`: investigation
      *started* at its first occurrence, the mitigation that held is the last
      one). Earlier occurrences stay as recorded - they are the history of the
      failed attempts, not a mistake to fix. When it never happened, the field
      is offered empty and filling it records that step. Such a field is
      optional; one that already has a time is required, since a transition
      that happened has to keep some time (drop it from the admin instead).
      `OPEN` and `POST_MORTEM` are never correction targets - see
      `_NON_EDITABLE_STATUSES`.
    """

    incident: Incident
    user: User

    field_prefix: str = ""
    """Prefixed to every field name, so each Slack surface owns its action ids."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.incident = kwargs.pop("incident")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self._milestone_updates = milestone_timestamps(self.incident)
        self._status_rows = self._collect_status_rows()
        self.generate_fields_dynamically()

    def generate_fields_dynamically(self) -> None:
        for spec in self._field_specs():
            self.fields[spec.name] = forms.DateTimeField(
                required=spec.required,
                # Slack itself appends "(optional)" next to the label for any
                # non-required field (see form_utils.py's optional=not
                # f.required) - adding it here too would show it twice.
                label=spec.label,
                widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
            )
            if spec.name not in self.initial:
                self.initial[spec.name] = spec.initial or ""

    def _field_specs(self) -> list[_FieldSpec]:
        editable_milestones = self._editable_milestones()
        known_event_types = {
            source for _label, _emoji, source, _req in EXPECTED_STEPS
            if isinstance(source, str)
        }
        extra_milestones = [
            milestone
            for event_type, milestone in editable_milestones.items()
            if event_type not in known_event_types
        ]

        specs: list[_FieldSpec] = []
        for _label, _emoji, source, _required in EXPECTED_STEPS:
            if isinstance(source, str):
                milestone = editable_milestones.get(source)
                if milestone is not None:
                    specs.append(self._milestone_spec(milestone))
                continue
            if source == _LAST_STEP_STATUS:
                specs += [
                    self._milestone_spec(milestone) for milestone in extra_milestones
                ]
            if source in _NON_EDITABLE_STATUSES:
                continue
            specs.append(self._status_spec(source))
        return specs

    def _editable_milestones(self) -> dict[str, MilestoneType]:
        return {
            milestone.event_type: milestone
            for milestone in MilestoneType.objects.filter(
                asked_for=True, user_editable=True
            ).order_by("id")
        }

    def _milestone_spec(self, milestone: MilestoneType) -> _FieldSpec:
        return _FieldSpec(
            name=f"{self.field_prefix}milestone_{milestone.event_type}",
            label=milestone.name,
            initial=self._milestone_updates.get(milestone.event_type),
            required=False,
        )

    def _status_spec(self, status: IncidentStatus) -> _FieldSpec:
        total, update = self._status_rows.get(status, (0, None))
        which = DEFINITIVE_OCCURRENCE.get(status, DEFAULT_OCCURRENCE)
        label = status.label if total <= 1 else f"{status.label} ({which} of {total})"
        return _FieldSpec(
            name=f"{self.field_prefix}status_{status.value}",
            label=label,
            initial=update.event_ts if update else None,
            required=update is not None,
        )

    def _collect_status_rows(self) -> dict[IncidentStatus, tuple[int, IncidentUpdate]]:
        """Per status, how many times it happened and which row is the definitive one."""
        totals: dict[IncidentStatus, int] = {}
        chosen: dict[IncidentStatus, IncidentUpdate] = {}
        for update in (
            self.incident.incidentupdate_set.filter(_status__isnull=False)
            .exclude(_status=IncidentStatus.OPEN)
            .order_by("event_ts")
        ):
            status = update.status
            if status is None:
                continue
            totals[status] = totals.get(status, 0) + 1
            which = DEFINITIVE_OCCURRENCE.get(status, DEFAULT_OCCURRENCE)
            if which == "last" or status not in chosen:
                chosen[status] = update
        return {status: (totals[status], update) for status, update in chosen.items()}

    def clean(self) -> dict[str, Any] | None:
        if self.user is None:
            raise forms.ValidationError("User is required")
        return super().clean()

    def save(self) -> None:
        """Save each changed field in place."""
        for field_name in self.changed_data:
            key = field_name.removeprefix(self.field_prefix)
            value = self.cleaned_data[field_name]
            if key.startswith("milestone_"):
                self._save_milestone(key.removeprefix("milestone_"), value)
            elif key.startswith("status_"):
                self._save_status(key.removeprefix("status_"), value)

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

    def _save_status(self, raw_status: str, value: datetime | None) -> None:
        try:
            status = IncidentStatus(int(raw_status))
        except ValueError:
            logger.warning("Ignoring unknown status field status_%s", raw_status)
            return
        if value is None:
            # Only reachable for a status that was never recorded: one that has a
            # time is a required field, so it cannot be emptied from here.
            return
        _total, update = self._status_rows.get(status, (0, None))
        if update is None:
            # The step was skipped when the incident ran (an incident going
            # straight from Declared to Mitigated, say) and is being filled in
            # after the fact. This records the step; it does not move the
            # incident, whose current status lives on the incident itself.
            IncidentUpdate.objects.create(
                incident_id=self.incident.id,
                _status=status,
                event_ts=value,
                created_by=self.user,
            )
            return
        IncidentUpdate.objects.filter(id=update.id).update(event_ts=value)


class KeyEventsTimelineForm(IncidentTimelineForm):
    """The same timeline, under the Key Events message's own action ids."""

    field_prefix = "key_event_"
