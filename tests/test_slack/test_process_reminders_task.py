"""The process reminder keeps nudging while an incident stalls, and stops as soon as it moves."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import (
    COMMANDER_ROLE_SLUG,
    IncidentRoleType,
)
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import (
    IncidentChannelFactory,
    MessageFactory,
    SlackConversationFactory,
    SlackUserFactory,
)
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentProcessReminder,
    SlackMessageIncidentProcessReminderAnnouncement,
)
from firefighter.slack.tasks.send_postmortem_reminders import send_postmortem_reminders

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident

FIRST_DELAY_SECONDS = 5 * 24 * 3600
REPEAT_DELAY_SECONDS = 3 * 24 * 3600


@pytest.fixture(autouse=True)
def _reminder_delays(settings):
    settings.FF_PROCESS_REMINDER_FIRST_DELAY = FIRST_DELAY_SECONDS
    settings.FF_PROCESS_REMINDER_REPEAT_DELAY = REPEAT_DELAY_SECONDS
    settings.ENABLE_JIRA_POSTMORTEM = True


def _mitigated_incident(
    *,
    priority_value: int = 1,
    mitigated_days_ago: float = 6,
    status: int = IncidentStatus.MITIGATED.value,
) -> Incident:
    incident = IncidentFactory.create(
        _status=status,
        priority=Priority.objects.get(value=priority_value),
        environment=Environment.objects.get(value="PRD"),
        mitigated_at=timezone.now() - timedelta(days=mitigated_days_ago),
        private=False,
    )
    IncidentChannelFactory.create(incident=incident)
    user = UserFactory.create()
    SlackUserFactory.create(user=user)
    IncidentRole.objects.create(
        incident=incident,
        user=user,
        role_type=IncidentRoleType.objects.get(slug=COMMANDER_ROLE_SLUG),
    )
    return incident


def _past_reminder(incident: Incident, *, days_ago: float) -> None:
    MessageFactory.create(
        incident=incident,
        conversation=incident.conversation,
        ff_type=SlackMessageIncidentProcessReminder.id,
        ts=timezone.now() - timedelta(days=days_ago),
    )


def _reminded_incidents(mock_send) -> list[int]:
    """Incident ids that got a process reminder in their own channel."""
    return [
        call.args[0].incident.id
        for call in mock_send.call_args_list
        if isinstance(call.args[0], SlackMessageIncidentProcessReminder)
    ]


@pytest.fixture
def mock_send():
    with patch(
        "firefighter.slack.models.conversation.Conversation.send_message_and_save"
    ) as mocked:
        yield mocked


@pytest.mark.django_db
class TestFirstReminder:
    def test_reminds_once_the_first_delay_has_passed(self, mock_send):
        incident = _mitigated_incident(mitigated_days_ago=6)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)

    def test_stays_quiet_before_the_first_delay(self, mock_send):
        incident = _mitigated_incident(mitigated_days_ago=2)

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_stays_quiet_on_ignored_incidents(self, mock_send):
        incident = _mitigated_incident()
        incident.ignore = True
        incident.save(update_fields=["ignore"])

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_stays_quiet_once_the_incident_is_closed(self, mock_send):
        incident = _mitigated_incident(status=IncidentStatus.CLOSED.value)

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)


@pytest.mark.django_db
class TestScope:
    @pytest.mark.parametrize("priority_value", [1, 2, 3])
    def test_p1_to_p3_are_reminded(self, mock_send, priority_value: int):
        incident = _mitigated_incident(priority_value=priority_value)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)

    @pytest.mark.parametrize("priority_value", [4, 5])
    def test_p4_and_p5_are_left_alone(self, mock_send, priority_value: int):
        incident = _mitigated_incident(priority_value=priority_value)

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_a_priority_requiring_a_post_mortem_stays_in_scope_whatever_its_value(
        self, mock_send
    ):
        # GAMEDAY sits at value 20, outside P1-P3, but is flagged as needing a post-mortem.
        gameday = Priority.objects.get(value=20)
        gameday.needs_postmortem = True
        gameday.save(update_fields=["needs_postmortem"])
        incident = _mitigated_incident(priority_value=20)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)


@pytest.mark.django_db
class TestRepeats:
    def test_stays_quiet_while_the_repeat_delay_has_not_elapsed(self, mock_send):
        incident = _mitigated_incident(mitigated_days_ago=10)
        _past_reminder(incident, days_ago=1)

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_reminds_again_once_the_process_has_been_still_for_the_repeat_delay(
        self, mock_send
    ):
        incident = _mitigated_incident(mitigated_days_ago=10)
        _past_reminder(incident, days_ago=4)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)

    def test_an_incident_update_restarts_the_clock(self, mock_send):
        incident = _mitigated_incident(mitigated_days_ago=10)
        _past_reminder(incident, days_ago=4)
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            created_by=UserFactory.create(),
            message="Post-mortem is being written",
        )

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_repeats_can_be_disabled(self, mock_send, settings):
        settings.FF_PROCESS_REMINDER_REPEAT_DELAY = 0
        incident = _mitigated_incident(mitigated_days_ago=30)
        _past_reminder(incident, days_ago=20)

        send_postmortem_reminders()

        assert incident.id not in _reminded_incidents(mock_send)

    def test_an_accelerated_cadence_reminds_within_minutes(self, mock_send, settings):
        settings.FF_PROCESS_REMINDER_FIRST_DELAY = 60
        settings.FF_PROCESS_REMINDER_REPEAT_DELAY = 120
        incident = _mitigated_incident(mitigated_days_ago=1 / 24)  # an hour ago
        _past_reminder(incident, days_ago=10 / (24 * 60))  # ten minutes ago

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)


def _announced_incidents(mock_send) -> list[int]:
    """Incident ids announced in #critical-incidents."""
    return [
        call.args[0].incident.id
        for call in mock_send.call_args_list
        if isinstance(call.args[0], SlackMessageIncidentProcessReminderAnnouncement)
    ]


@pytest.mark.django_db
class TestPublicAnnouncement:
    @pytest.fixture(autouse=True)
    def _tech_incidents_channel(self):
        return SlackConversationFactory.create(tag="tech_incidents")

    def test_the_first_reminder_is_announced(self, mock_send):
        incident = _mitigated_incident(priority_value=1)

        send_postmortem_reminders()

        assert incident.id in _announced_incidents(mock_send)

    def test_repeats_stay_in_the_incident_channel(self, mock_send):
        incident = _mitigated_incident(priority_value=1, mitigated_days_ago=10)
        _past_reminder(incident, days_ago=4)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)
        assert incident.id not in _announced_incidents(mock_send)

    def test_p3_is_reminded_without_being_announced(self, mock_send):
        incident = _mitigated_incident(priority_value=3)

        send_postmortem_reminders()

        assert incident.id in _reminded_incidents(mock_send)
        assert incident.id not in _announced_incidents(mock_send)
