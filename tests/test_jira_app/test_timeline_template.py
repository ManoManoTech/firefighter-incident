"""Tests for Jira post-mortem timeline template rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.jira_app.service_postmortem import build_timeline_rows

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestTimelineTemplate:
    """Test timeline template rendering with chronological ordering."""

    @staticmethod
    def test_timeline_includes_key_events_and_status_changes() -> None:
        """Test that timeline includes both key events and status changes in chronological order."""
        # Create a user
        user: User = UserFactory.create()

        # Create an incident
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Event 0: declared (key event) - always the first row, at created_at
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="declared",
            event_ts=incident.created_at,
            created_by=user,
        )

        # Create key events and status changes at different times
        base_time = timezone.now()

        # Event 1: detected (key event) - earliest
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=base_time,
            created_by=user,
            message="Issue was detected",
        )

        # Event 2: status change to INVESTIGATING - middle
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time + timezone.timedelta(minutes=5),
            created_by=user,
        )

        # Event 3: started (key event) - later
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=base_time + timezone.timedelta(minutes=10),
            created_by=user,
            message="Investigation started",
        )

        # Event 4: status change to MITIGATING - latest
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=15),
            created_by=user,
        )

        # Render the timeline template
        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"timeline_rows": build_timeline_rows(incident)},
        )

        # Verify timeline contains all events
        assert "Key event: Declared" in timeline_content
        assert "Key event: Detected" in timeline_content
        assert "Issue was detected" in timeline_content
        assert "Status changed to: Investigating" in timeline_content
        assert "Key event: Started" in timeline_content
        assert "Investigation started" in timeline_content
        assert "Status changed to: Mitigating" in timeline_content

        # Verify chronological order by checking positions in the timeline
        # The events should appear in this order:
        # 1. declared (key event)
        # 2. detected (key event)
        # 3. INVESTIGATING (status change)
        # 4. started (key event)
        # 5. MITIGATING (status change)
        declared_pos = timeline_content.find("Key event: Declared")
        detected_pos = timeline_content.find("Key event: Detected")
        investigating_pos = timeline_content.find("Status changed to: Investigating")
        started_pos = timeline_content.find("Key event: Started")
        mitigating_pos = timeline_content.find("Status changed to: Mitigating")

        assert declared_pos < detected_pos < investigating_pos < started_pos < mitigating_pos, (
            "Events are not in chronological order"
        )

    @staticmethod
    def test_timeline_handles_key_events_without_message() -> None:
        """Test that timeline handles key events that have no message."""
        # Create a user
        user: User = UserFactory.create()

        # Create an incident
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        # Create a key event without message
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=timezone.now(),
            created_by=user,
            message=None,
        )

        # Render the timeline template
        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"timeline_rows": build_timeline_rows(incident)},
        )

        # Verify the key event appears without a dash for empty message
        assert "Key event: Detected" in timeline_content
        # Should not have " - " when there's no message
        assert "Key event: Detected -" not in timeline_content

    @staticmethod
    def test_backfilled_milestone_before_created_at_sorts_first() -> None:
        """A Started/Detected time backfilled to before created_at must lead the timeline.

        Regression test: "Incident created" used to be hardcoded as the first
        row regardless of actual event_ts, which put backfilled milestones
        (routinely earlier than when the incident was declared in
        FireFighter) out of order.
        """
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )

        IncidentUpdate.objects.create(
            incident=incident,
            event_type="declared",
            event_ts=incident.created_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=incident.created_at - timezone.timedelta(hours=2),
            created_by=user,
        )

        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"timeline_rows": build_timeline_rows(incident)},
        )

        started_pos = timeline_content.find("Key event: Started")
        declared_pos = timeline_content.find("Key event: Declared")

        assert started_pos < declared_pos, (
            "Backfilled 'Started' milestone must appear before 'Declared'"
        )

    @staticmethod
    @override_settings(TIME_ZONE="Europe/Paris")
    def test_times_are_rendered_in_active_timezone_not_mislabeled_utc() -> None:
        """Regression: template used to hardcode " UTC" while actually rendering
        the active timezone (TIME_ZONE setting), mismatching the label against
        the real converted time - e.g. a 09:00 UTC event rendered as "10:00 UTC"
        (Paris local time) instead of the correct "10:00 CET".
        """
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )
        incident.created_at = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
        incident.save()
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="declared",
            event_ts=incident.created_at,
            created_by=user,
        )

        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"timeline_rows": build_timeline_rows(incident)},
        )

        # Europe/Paris is UTC+1 in January (CET, no DST).
        assert "2026-01-15 10:00 CET" in timeline_content
        assert "UTC" not in timeline_content

    @staticmethod
    def test_reopen_to_open_shows_as_a_status_change() -> None:
        """A later, genuine reopen to OPEN is a real transition, not the declaration.

        The OPEN row created at declaration time (same `event_ts` as the
        "declared" key event) is folded into "Key event: Declared" and must
        not also render as "Status changed to: Open". But an incident can go
        back to OPEN later - that row has a different `event_ts` and must
        still show up as its own "Status changed to: Open" line.
        """
        user: User = UserFactory.create()
        incident: Incident = IncidentFactory.create(
            _status=IncidentStatus.OPEN,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=incident.created_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="declared",
            event_ts=incident.created_at,
            created_by=user,
        )
        reopened_at = incident.created_at + timezone.timedelta(days=1)
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=reopened_at,
            created_by=user,
        )

        timeline_content = render_to_string(
            "jira/postmortem/timeline.txt",
            {"timeline_rows": build_timeline_rows(incident)},
        )

        assert timeline_content.count("Status changed to: Open") == 1
        assert "Key event: Declared" in timeline_content
