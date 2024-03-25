from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.milestone_type import (
    MilestoneData,
    MilestoneType,
    MilestoneTypeData,
)

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from django.forms import Field

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


class IncidentUpdateKeyEventsForm(forms.Form):
    incident: Incident
    user: User
    initial: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.incident = kwargs.pop("incident")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.generate_fields_dynamically()

    def generate_fields_dynamically(self) -> None:
        milestones_definitions_base = MilestoneType.objects.filter(asked_for=True)
        milestones_definitions = self.get_milestones_with_data(
            milestones_definitions_base
        )

        for key_event in milestones_definitions:
            field_name = f"key_event_{key_event.milestone_type.event_type}"
            self.fields[field_name] = forms.DateTimeField(
                required=False,
                disabled=not key_event.milestone_type.user_editable,
                label=key_event.milestone_type.summary
                + (" _(optional)_" if not key_event.milestone_type.required else ""),
                widget=forms.DateTimeInput(
                    attrs={
                        "placeholder": key_event.milestone_type.event_type,
                        "type": "datetime-local",
                    }
                ),
            )

            if field_name not in self.initial:
                try:
                    self.initial[field_name] = key_event.data.event_ts
                except IndexError:
                    self.initial[field_name] = ""
            logger.debug(f"Initial {field_name} was set to {self.initial[field_name]}")

    def clean(self) -> dict[str, Any] | None:
        if self.user is None:
            raise forms.ValidationError("User is required")
        # XXX TODO Validate that all required key events are present, and in the good order
        # XXX Validate that we have all fields and no extra fields
        return super().clean()

    def save(self) -> None:
        """Custom save method to save each changed key event."""
        self.fields: dict[str, Field]
        for field_name in self.fields:
            if field_name not in self.changed_data or self.fields[field_name].disabled:
                logger.debug("skipping %s", field_name)
                continue
            if not field_name.startswith("key_event_"):
                continue

            key_event_type = field_name.replace("key_event_", "")

            logger.debug(f"save {field_name} {self.cleaned_data[field_name]}")
            self._save_key_event(key_event_type, self.cleaned_data[field_name])

    def _save_key_event(
        self, key_event_type: str, value: datetime | None
    ) -> tuple[int, dict[str, int]] | tuple[IncidentUpdate, bool]:
        if value is None:
            return IncidentUpdate.objects.filter(
                incident_id=self.incident.id, event_type=key_event_type
            ).delete()

        return IncidentUpdate.objects.update_or_create(
            incident_id=self.incident.id,
            event_type=key_event_type,
            defaults={"event_ts": value, "created_by": self.user},
        )

    def get_milestones_with_data(
        self,
        milestones_definitions: Iterable[MilestoneType],
    ) -> list[MilestoneTypeData]:
        """Get each [firefighter.incidents.models.milestone_type.MilestoneType][] with its `event_ts` from the IncidentUpdate."""
        milestones_objects = self.incident.latest_updates_by_type
        ass = []
        for milestone_def in milestones_definitions:
            event = milestones_objects.get(milestone_def.event_type)
            event_ts = event.event_ts if event and event.event_ts else None
            association = MilestoneTypeData(
                milestone_type=milestone_def, data=MilestoneData(event_ts)
            )
            ass.append(association)
        return ass
