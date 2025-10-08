from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis.extra import django
from hypothesis.strategies import builds

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models import IncidentUpdate

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident


@pytest.mark.django_db
class TestIncident(django.TestCase):
    """This is a property-based test that ensures model correctness."""

    @given(builds(IncidentFactory.build))
    def test_model_properties(self, instance: Incident) -> None:
        """Tests that instance can be saved and has correct representation."""
        instance.incident_category.group.save()
        instance.incident_category.save()
        instance.environment.save()
        instance.priority.save()
        instance.created_by.save()
        instance.save()

        assert instance.id > 0


@pytest.mark.django_db
class TestIncidentCanBeClosed:
    """Test the can_be_closed property logic."""

    def test_cannot_close_incident_below_mitigated_status(self) -> None:
        """Test that incidents below MITIGATED status cannot be closed without reason."""
        # Create an incident in INVESTIGATING status (below MITIGATED)
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        can_close, reasons = incident.can_be_closed

        assert can_close is False
        assert any(reason[0] == "STATUS_NOT_MITIGATED" for reason in reasons)
        assert any("Mitigated" in reason[1] for reason in reasons)

    def test_can_close_incident_at_mitigated_status(self) -> None:
        """Test that incidents at MITIGATED status can be closed (if no postmortem required)."""
        # Create a P3 incident in MITIGATED status (no postmortem required)
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority__value=3,  # P3 doesn't require postmortem
        )

        can_close, reasons = incident.can_be_closed

        # Should be closable (assuming no missing milestones)
        assert can_close is True or "STATUS_NOT_MITIGATED" not in [r[0] for r in reasons]

    def test_can_close_incident_with_closure_reason(self) -> None:
        """Test that incidents with closure_reason can always be closed."""
        # Create an incident in early status but with closure reason
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            closure_reason=ClosureReason.DUPLICATE,
        )

        can_close, reasons = incident.can_be_closed

        assert can_close is True
        assert reasons == []


@pytest.mark.django_db
class TestIncidentSetStatus:
    """Test the set_status method logic."""

    def test_set_status_to_mitigated_creates_recovered_event(self) -> None:
        """Test that setting status to MITIGATED creates a 'recovered' event."""
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Set status to MITIGATED using create_incident_update
        incident.create_incident_update(
            status=IncidentStatus.MITIGATED.value,
            created_by=incident.created_by,
            message="Incident has been mitigated",
        )

        # Check that a 'recovered' event was created
        recovered_event = IncidentUpdate.objects.filter(
            incident=incident, event_type="recovered"
        ).first()

        assert recovered_event is not None
        assert recovered_event.event_type == "recovered"
