from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.forms.timeline_correction import TimelineCorrectionForm
from firefighter.incidents.models.incident_update import IncidentUpdate

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestGenerateFieldsDynamically:
    @staticmethod
    def test_generates_a_field_per_milestone_and_per_status_reached() -> None:
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

        form = TimelineCorrectionForm(incident=incident, user=user)

        assert "milestone_started" in form.fields
        assert form.initial["milestone_started"] == started_update.event_ts
        assert "milestone_detected" in form.fields
        assert form.initial["milestone_detected"] == ""

        assert f"status_{investigating_update.id}" in form.fields
        assert (
            form.initial[f"status_{investigating_update.id}"]
            == investigating_update.event_ts
        )

    @staticmethod
    def test_open_has_no_editable_field() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = TimelineCorrectionForm(incident=incident, user=user)

        # OPEN is anchored to incident.created_at, never a recorded row -
        # there must be no status field for it.
        assert not any(
            name.startswith("status_") and IncidentStatus.OPEN.label in str(field.label)
            for name, field in form.fields.items()
        )
        assert len(form.fields) == 2 + 1  # 2 milestones + 1 status (MITIGATED)

    @staticmethod
    def test_status_fields_are_required_milestones_are_optional() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = TimelineCorrectionForm(incident=incident, user=user)

        assert form.fields[f"status_{update.id}"].required is True
        assert form.fields["milestone_started"].required is False

    @staticmethod
    def test_reopen_exposes_one_field_per_occurrence_numbered() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        base_time = timezone.now()
        first_mitigating = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time,
            created_by=user,
        )
        second_mitigating = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=30),
            created_by=user,
        )

        form = TimelineCorrectionForm(incident=incident, user=user)

        mitigating_fields = [
            name for name in form.fields if name.startswith("status_")
        ]
        assert mitigating_fields == [
            f"status_{first_mitigating.id}",
            f"status_{second_mitigating.id}",
        ]
        assert form.fields[f"status_{first_mitigating.id}"].label == "Mitigating (1)"
        assert form.fields[f"status_{second_mitigating.id}"].label == "Mitigating (2)"

    @staticmethod
    def test_status_reached_once_keeps_a_bare_label() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )

        form = TimelineCorrectionForm(incident=incident, user=user)

        assert form.fields[f"status_{update.id}"].label == "Mitigated"


@pytest.mark.django_db
class TestSave:
    @staticmethod
    def test_creates_a_milestone_that_was_never_recorded() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user: User = UserFactory.create()
        new_time = timezone.now()

        form = TimelineCorrectionForm(
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

        form = TimelineCorrectionForm(
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

        form = TimelineCorrectionForm(
            data={f"status_{update.id}": corrected_time.isoformat()},
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
    def test_requires_a_user() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = TimelineCorrectionForm(data={}, incident=incident)

        assert not form.is_valid()
