"""Tests for the shared incident timeline: its canonical steps and their order."""

from __future__ import annotations

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.timeline import (
    TimelineEntry,
    TimelineStep,
    find_timeline_issues,
    get_canonical_steps,
    get_incident_timeline,
    get_status_timeline,
)


@pytest.mark.django_db
class TestGetStatusTimeline:
    @staticmethod
    def test_open_anchors_to_created_at_even_if_declaration_row_differs() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()

        # The declaration's own OPEN row, at the same instant as created_at -
        # this is the row the anchor represents, so it must not double up.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=incident.created_at,
            created_by=user,
        )

        timeline = get_status_timeline(incident)
        assert timeline == [(IncidentStatus.OPEN, incident.created_at)]

    @staticmethod
    def test_reopen_to_open_shows_as_its_own_later_entry() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()
        reopened_at = incident.created_at + timezone.timedelta(days=1)

        # A genuine reopen back to OPEN, distinct from the declaration.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=reopened_at,
            created_by=user,
        )

        timeline = get_status_timeline(incident)

        assert timeline == [
            (IncidentStatus.OPEN, incident.created_at),
            (IncidentStatus.OPEN, reopened_at),
        ]

    @staticmethod
    def test_reopen_loop_includes_every_occurrence_chronologically() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        base_time = timezone.now()

        # First pass: INVESTIGATING -> MITIGATING -> MITIGATED
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=10),
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=base_time + timezone.timedelta(minutes=20),
            created_by=user,
        )
        # Reopen: back to INVESTIGATING, then MITIGATING, then MITIGATED again.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time + timezone.timedelta(minutes=30),
            created_by=user,
            message="Reopening: found a regression.",
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=40),
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=base_time + timezone.timedelta(minutes=50),
            created_by=user,
        )

        timeline = get_status_timeline(incident)
        statuses = [status for status, _ in timeline]

        # Every occurrence is kept, in chronological order - including the
        # full reopen cycle, matching the Jira post-mortem timeline.
        assert statuses == [
            IncidentStatus.OPEN,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
            IncidentStatus.MITIGATED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
            IncidentStatus.MITIGATED,
        ]

        event_timestamps = [event_ts for _, event_ts in timeline]
        assert event_timestamps == [
            incident.created_at,
            base_time,
            base_time + timezone.timedelta(minutes=10),
            base_time + timezone.timedelta(minutes=20),
            base_time + timezone.timedelta(minutes=30),
            base_time + timezone.timedelta(minutes=40),
            base_time + timezone.timedelta(minutes=50),
        ]


@pytest.mark.django_db
class TestGetIncidentTimeline:
    @staticmethod
    def test_includes_recorded_milestones_before_status_timeline() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        started_at = incident.created_at - timezone.timedelta(hours=2)
        detected_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=started_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Started", event_ts=started_at)
        assert timeline[1] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[2].label == "Declared"
        assert timeline[2].event_ts == incident.created_at

    @staticmethod
    def test_missing_milestones_show_as_not_recorded() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Started", event_ts=None)
        assert timeline[1] == TimelineEntry(label="Detected", event_ts=None)

    @staticmethod
    def test_milestones_sort_chronologically_among_themselves() -> None:
        """Detected can legitimately be recorded before Started (e.g. an
        automated alert fires before the actual start is pinpointed) - the
        milestone group must reflect that, not the fixed Started-then-Detected
        declaration order.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        detected_at = incident.created_at - timezone.timedelta(hours=2)
        started_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=started_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[1] == TimelineEntry(label="Started", event_ts=started_at)

    @staticmethod
    def test_unrecorded_milestone_sorts_after_a_recorded_one() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        detected_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[1] == TimelineEntry(label="Started", event_ts=None)

    @staticmethod
    def test_only_the_first_open_is_labeled_declared() -> None:
        """A later reopen to OPEN is a real status, not the declaration - it
        must keep reading "Open", not "Declared" a second time.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()
        reopened_at = incident.created_at + timezone.timedelta(days=1)
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=reopened_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)
        status_entries = timeline[2:]

        assert status_entries == [
            TimelineEntry(label="Declared", event_ts=incident.created_at),
            TimelineEntry(label="Open", event_ts=reopened_at),
        ]


@pytest.mark.django_db
class TestRecoveredStep:
    """Recovered closes the timeline: it is where the SLA clock stops.

    `time_to_fix` is `Recovered - Declared`, so an incident without Recovered
    cannot be graded against its target at all - hence required. But it is
    business time typed by hand, while Mitigated is a status transition clicked
    in Slack: on the support data the two share a timestamp on 77% of
    incidents, Recovered comes first on 19.6% and later on 3.2%. Ordering it
    against its neighbour would flag one incident in five for nothing.
    """

    @staticmethod
    def _steps(incident: Incident) -> list[TimelineStep]:
        return get_canonical_steps(incident)

    @staticmethod
    def test_missing_recovered_is_reported() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        for event_type in ("started", "detected"):
            IncidentUpdate.objects.create(
                incident=incident,
                event_type=event_type,
                event_ts=incident.created_at - timezone.timedelta(hours=1),
                created_by=user,
            )

        issues = find_timeline_issues(get_canonical_steps(incident))

        assert any(
            "Recovered" in issue.message and "required" in issue.message
            for issue in issues
        )

    @staticmethod
    @pytest.mark.parametrize("offset_minutes", [-30, 0, 30])
    def test_recovered_is_not_ordered_against_mitigated(offset_minutes: int) -> None:
        """Before, at the same instant, or after: none of them is an issue."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        # `created_at` is auto_now_add, so the whole timeline is pushed into
        # yesterday - otherwise anything after the declaration reads as future.
        Incident.objects.filter(pk=incident.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=1)
        )
        incident.refresh_from_db()
        user = UserFactory.create()
        mitigated_at = incident.created_at + timezone.timedelta(hours=2)
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=mitigated_at,
            created_by=user,
        )
        for event_type, ts in (
            ("started", incident.created_at - timezone.timedelta(hours=2)),
            ("detected", incident.created_at - timezone.timedelta(hours=1)),
            (
                "recovered",
                mitigated_at + timezone.timedelta(minutes=offset_minutes),
            ),
        ):
            IncidentUpdate.objects.create(
                incident=incident, event_type=event_type, event_ts=ts, created_by=user
            )

        issues = find_timeline_issues(get_canonical_steps(incident))

        assert [issue for issue in issues if issue.label == "Recovered"] == []

    @staticmethod
    def test_recovered_before_the_declaration_is_reported() -> None:
        """`time_to_fix` would be negative - the metric itself refuses that."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        for event_type, ts in (
            ("started", incident.created_at - timezone.timedelta(hours=3)),
            ("detected", incident.created_at - timezone.timedelta(hours=2)),
            ("recovered", incident.created_at - timezone.timedelta(hours=1)),
        ):
            IncidentUpdate.objects.create(
                incident=incident, event_type=event_type, event_ts=ts, created_by=user
            )

        issues = find_timeline_issues(get_canonical_steps(incident))

        assert any(
            issue.label == "Recovered" and "before *Declared*" in issue.message
            for issue in issues
        )

    @staticmethod
    def test_recovered_is_read_back_into_the_canonical_steps() -> None:
        """It used to be fetched by no one, so the form always showed it empty."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        recovered_at = incident.created_at + timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="recovered",
            event_ts=recovered_at,
            created_by=UserFactory.create(),
        )

        step = next(
            step for step in get_canonical_steps(incident) if step.label == "Recovered"
        )

        assert step.event_ts == recovered_at
        assert step.required is True
