"""The update reminder is only posted in channels that can still receive messages."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.models.conversation import ConversationStatus
from firefighter.slack.tasks.send_reminders import send_reminders


@pytest.fixture(autouse=True)
def office_hours_gate():
    with patch(
        "firefighter.slack.tasks.send_reminders.is_during_office_hours",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_group():
    with patch("firefighter.slack.tasks.send_reminders.group") as mocked:
        yield mocked


def _stale_incident() -> Incident:
    """An open P1 whose last update is older than its priority's reminder delay."""
    priority = Priority.objects.get(value=1)
    incident = IncidentFactory.create(
        _status=IncidentStatus.INVESTIGATING.value,
        priority=priority,
        environment=Environment.objects.get(value="PRD"),
        private=False,
    )
    IncidentChannelFactory.create(incident=incident)
    update = IncidentUpdate.objects.create(incident=incident)
    IncidentUpdate.objects.filter(pk=update.pk).update(
        created_at=timezone.now() - priority.reminder_time - timedelta(hours=1)
    )
    return incident


def _reminded_channels(mock_group) -> list[str]:
    (signatures,), _ = mock_group.call_args
    return [chain.tasks[0].kwargs["channel"] for chain in signatures]


@pytest.mark.django_db
def test_reminds_a_stale_incident(mock_group):
    incident = _stale_incident()

    send_reminders()

    assert _reminded_channels(mock_group) == [incident.conversation.channel_id]


@pytest.mark.django_db
def test_skips_an_incident_whose_channel_is_archived(mock_group):
    incident = _stale_incident()
    incident.conversation.status = ConversationStatus.ARCHIVED
    incident.conversation.save()

    send_reminders()

    assert _reminded_channels(mock_group) == []
