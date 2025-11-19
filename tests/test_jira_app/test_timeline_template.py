"""Tests for Jira post-mortem timeline template rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_update import IncidentUpdate

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
            {"incident": incident},
        )

        # Verify timeline contains all events
        assert "Incident created" in timeline_content
        assert "Key event: Detected" in timeline_content
        assert "Issue was detected" in timeline_content
        assert "Status changed to: Investigating" in timeline_content
        assert "Key event: Started" in timeline_content
        assert "Investigation started" in timeline_content
        assert "Status changed to: Mitigating" in timeline_content

        # Verify chronological order by checking positions in the timeline
        # The events should appear in this order:
        # 1. Incident created
        # 2. detected (key event)
        # 3. INVESTIGATING (status change)
        # 4. started (key event)
        # 5. MITIGATING (status change)
        created_pos = timeline_content.find("Incident created")
        detected_pos = timeline_content.find("Key event: Detected")
        investigating_pos = timeline_content.find("Status changed to: Investigating")
        started_pos = timeline_content.find("Key event: Started")
        mitigating_pos = timeline_content.find("Status changed to: Mitigating")

        assert created_pos < detected_pos < investigating_pos < started_pos < mitigating_pos, (
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
            {"incident": incident},
        )

        # Verify the key event appears without a dash for empty message
        assert "Key event: Detected" in timeline_content
        # Should not have " - " when there's no message
        assert "Key event: Detected -" not in timeline_content
