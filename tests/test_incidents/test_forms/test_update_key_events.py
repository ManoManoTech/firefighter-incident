from __future__ import annotations

from datetime import UTC, datetime

import pytest

from firefighter.incidents.forms.update_key_events import IncidentUpdateKeyEventsForm
from firefighter.incidents.models import Incident, User
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.milestone_type import MilestoneType


@pytest.fixture
def user() -> User:
    return User.objects.create_user(username="testuser")


@pytest.fixture
def milestone_type() -> MilestoneType:
    return MilestoneType(
        event_type="detected",
        name="Test Event",
        user_editable=True,
        required=True,
        asked_for=True,
    )


@pytest.mark.django_db
def test_incident_update_key_events_form(
    user: User, incident_saved: Incident, milestone_type: MilestoneType
):
    # Setup
    incident = incident_saved

    form_data = {f"key_event_{milestone_type.event_type}": "2023-04-08T18:00:00Z"}
    form = IncidentUpdateKeyEventsForm(data=form_data, incident=incident, user=user)

    # Test form validity and save
    assert form.is_valid()
    form.save()

    # Check if IncidentUpdate is created with the correct data
    incident_update = IncidentUpdate.objects.filter(
        incident=incident, event_type=milestone_type.event_type
    ).first()
    assert incident_update is not None
    assert incident_update.event_ts == datetime(2023, 4, 8, 18, 0, tzinfo=UTC)
    assert incident_update.created_by == user

    # Test form with missing user
    form_without_user = IncidentUpdateKeyEventsForm(data=form_data, incident=incident)
    assert not form_without_user.is_valid()
