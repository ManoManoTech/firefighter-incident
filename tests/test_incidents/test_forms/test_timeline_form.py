"""Tests for the shared timeline form, used by both Slack timeline surfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.forms.timeline import (
    IncidentTimelineForm,
    KeyEventsTimelineForm,
)
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.timeline import STATUS_HINTS

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestGenerateFieldsDynamically:
    @staticmethod
    def test_offers_every_key_event_even_the_ones_never_reached() -> None:
        """The whole timeline is correctable, not only what happened to be recorded."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()

        form = IncidentTimelineForm(incident=incident, user=user)

        assert list(form.fields) == [
            "milestone_started",
            "milestone_detected",
            f"status_{IncidentStatus.INVESTIGATING.value}",
            f"status_{IncidentStatus.MITIGATING.value}",
            f"status_{IncidentStatus.MITIGATED.value}",
            # Editable milestones outside the seven canonical steps come before
            # Post-mortem, which closes the sequence.
            "milestone_recovered",
        ]

    @staticmethod
    def test_takes_its_initial_values_from_what_was_recorded() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        started_update = IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=timezone.now() - timezone.timedelta(hours=2),
            created_by=user,
        )
        investigating_update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=timezone.now() - timezone.timedelta(hours=1),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        assert form.initial["milestone_started"] == started_update.event_ts
        assert form.initial["milestone_detected"] == ""
        investigating = f"status_{IncidentStatus.INVESTIGATING.value}"
        assert form.initial[investigating] == investigating_update.event_ts

    @staticmethod
    def test_open_has_no_editable_field() -> None:
        """The declaration is anchored to `created_at`, and a reopen is history."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        assert f"status_{IncidentStatus.OPEN.value}" not in form.fields

    @staticmethod
    def test_post_mortem_is_shown_but_not_editable() -> None:
        """It is stamped by the transition itself; there is nothing to correct."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.POST_MORTEM,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        assert f"status_{IncidentStatus.POST_MORTEM.value}" not in form.fields

    @staticmethod
    def test_non_editable_milestones_are_left_out() -> None:
        # `Declared` is not user_editable: it is the incident's declaration time.
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = IncidentTimelineForm(incident=incident, user=UserFactory.create())

        assert "milestone_declared" not in form.fields

    @staticmethod
    def test_a_recorded_status_is_required_everything_else_is_optional() -> None:
        """A transition that happened has to keep some time; the rest can stay blank."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        assert form.fields[f"status_{IncidentStatus.MITIGATED.value}"].required is True
        assert (
            form.fields[f"status_{IncidentStatus.MITIGATING.value}"].required is False
        )
        assert form.fields["milestone_started"].required is False

    @staticmethod
    def test_reopen_binds_mitigating_to_its_last_occurrence() -> None:
        """Mitigating settles on its last occurrence: that is the editable one."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        base_time = timezone.now()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time,
            created_by=user,
        )
        last_mitigating = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=30),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        field_name = f"status_{IncidentStatus.MITIGATING.value}"
        assert form.fields[field_name].label == "Mitigating (last of 2)"
        assert form.initial[field_name] == last_mitigating.event_ts

    @staticmethod
    def test_reopen_binds_investigating_to_its_first_occurrence() -> None:
        """Investigating started at its first occurrence, not at the last cycle."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        base_time = timezone.now()
        first_investigating = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time + timezone.timedelta(minutes=30),
            created_by=user,
        )

        field_name = f"status_{IncidentStatus.INVESTIGATING.value}"
        form = IncidentTimelineForm(incident=incident, user=user)

        assert form.fields[field_name].label == "Investigating (first of 2)"
        assert form.initial[field_name] == first_investigating.event_ts

    @staticmethod
    def test_status_reached_once_keeps_a_bare_label() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = IncidentTimelineForm(incident=incident, user=user)

        assert form.fields[f"status_{IncidentStatus.MITIGATED.value}"].label == (
            "Mitigated"
        )

    @staticmethod
    def test_every_field_carries_the_definition_of_its_key_event() -> None:
        """A key event is only recorded consistently if everyone reads it alike."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = IncidentTimelineForm(incident=incident, user=UserFactory.create())

        assert (
            form.fields["milestone_started"].help_text
            == "When the first issues arose."
        )
        assert (
            form.fields[f"status_{IncidentStatus.MITIGATING.value}"].help_text
            == STATUS_HINTS[IncidentStatus.MITIGATING]
        )
        # Every one of them, and none carrying the Markdown of the web labels:
        # Slack renders a hint as plain text.
        assert all(field.help_text for field in form.fields.values())
        assert all("*" not in field.help_text for field in form.fields.values())

    @staticmethod
    def test_both_surfaces_render_the_very_same_fields() -> None:
        """Mitigated posts the Key Events message, Post-mortem the correction one.

        They must be the same form: same key events, same order, same labels -
        only the prefix that routes an edit back to its own message differs.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=timezone.now(),
            created_by=user,
        )

        correction = IncidentTimelineForm(incident=incident, user=user)
        key_events = KeyEventsTimelineForm(incident=incident, user=user)

        assert [
            name.removeprefix(KeyEventsTimelineForm.field_prefix)
            for name in key_events.fields
        ] == list(correction.fields)
        assert [field.label for field in key_events.fields.values()] == [
            field.label for field in correction.fields.values()
        ]
        assert [field.required for field in key_events.fields.values()] == [
            field.required for field in correction.fields.values()
        ]

    @staticmethod
    def test_the_key_events_surface_gets_its_own_action_ids() -> None:
        """Two messages render this form; an edit must route back to its own."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = KeyEventsTimelineForm(incident=incident, user=UserFactory.create())

        assert all(name.startswith("key_event_") for name in form.fields)
        assert "key_event_milestone_started" in form.fields
        assert f"key_event_status_{IncidentStatus.MITIGATED.value}" in form.fields


@pytest.mark.django_db
class TestSave:
    @staticmethod
    def test_creates_a_milestone_that_was_never_recorded() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        new_time = timezone.now()

        form = IncidentTimelineForm(
            data={"milestone_started": new_time.isoformat()},
            incident=incident,
            user=user,
        )
        assert form.is_valid(), form.errors

        form.save()

        update = IncidentUpdate.objects.get(incident=incident, event_type="started")
        assert update.event_ts == new_time
        assert update.created_by == user

    @staticmethod
    def test_clearing_a_milestone_deletes_it() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=timezone.now(),
            created_by=user,
        )

        form = IncidentTimelineForm(
            data={"milestone_started": ""}, incident=incident, user=user
        )
        assert form.is_valid(), form.errors

        form.save()

        assert not IncidentUpdate.objects.filter(
            incident=incident, event_type="started"
        ).exists()

    @staticmethod
    def test_edits_the_status_row_in_place_without_creating_a_new_one() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )
        corrected_time = update.event_ts - timezone.timedelta(hours=1)

        form = IncidentTimelineForm(
            data={
                f"status_{IncidentStatus.MITIGATED.value}": corrected_time.isoformat()
            },
            incident=incident,
            user=user,
        )
        assert form.is_valid(), form.errors

        form.save()

        assert (
            IncidentUpdate.objects.filter(
                incident=incident, _status=IncidentStatus.MITIGATED
            ).count()
            == 1
        )
        update.refresh_from_db()
        assert update.event_ts == corrected_time

    @staticmethod
    def test_records_a_status_the_incident_never_went_through() -> None:
        """An incident that jumped straight to Mitigated can still be completed."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        investigating_at = timezone.now() - timezone.timedelta(hours=1)

        form = IncidentTimelineForm(
            data={
                f"status_{IncidentStatus.INVESTIGATING.value}": (
                    investigating_at.isoformat()
                )
            },
            incident=incident,
            user=user,
        )
        assert form.is_valid(), form.errors

        form.save()

        update = IncidentUpdate.objects.get(
            incident=incident, _status=IncidentStatus.INVESTIGATING
        )
        assert update.event_ts == investigating_at
        assert update.created_by == user

    @staticmethod
    def test_recording_a_status_does_not_move_the_incident() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user: User = UserFactory.create()

        form = IncidentTimelineForm(
            data={
                f"status_{IncidentStatus.MITIGATED.value}": timezone.now().isoformat()
            },
            incident=incident,
            user=user,
        )
        assert form.is_valid(), form.errors

        form.save()

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.OPEN

    @staticmethod
    def test_the_key_events_surface_saves_the_same_rows() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        mitigated_at = timezone.now()

        form = KeyEventsTimelineForm(
            data={
                f"key_event_status_{IncidentStatus.MITIGATED.value}": (
                    mitigated_at.isoformat()
                )
            },
            incident=incident,
            user=user,
        )
        assert form.is_valid(), form.errors

        form.save()

        update = IncidentUpdate.objects.get(
            incident=incident, _status=IncidentStatus.MITIGATED
        )
        assert update.event_ts == mitigated_at

    @staticmethod
    def test_requires_a_user() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = IncidentTimelineForm(data={}, incident=incident)

        assert not form.is_valid()
