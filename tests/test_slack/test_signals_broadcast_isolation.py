"""Tests that broadcast publications cannot suppress incident-channel publications."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.incident_channel import IncidentChannel

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

BROADCAST_TARGET = (
    "firefighter.slack.signals.incident_updated.publish_update_in_general_channel"
)
INCIDENT_CHANNEL_TARGET = (
    "firefighter.slack.signals.incident_updated.publish_incident_channel_update"
)


def _neutralise_channel_maintenance(mocker: MockerFixture) -> None:
    """Stub the Slack channel-maintenance calls that run before any publication."""
    mocker.patch.object(IncidentChannel, "rename_if_needed")
    mocker.patch.object(IncidentChannel, "set_incident_channel_topic")


def _mitigating_incident():
    """Build a saved P1/PRD incident with a channel, one step before MITIGATED."""
    user = UserFactory.build()
    user.save()
    incident = IncidentFactory.build(
        priority=Priority.objects.get(name="P1"),
        environment=Environment.objects.get(value="PRD"),
        created_by=user,
        private=False,
        _status=IncidentStatus.MITIGATING,
    )
    incident.save()
    channel = IncidentChannelFactory.build(incident=incident)
    channel.save()
    return incident, user


def _sent_message_types(mock_send) -> list[str]:
    types = []
    for call in mock_send.call_args_list:
        message = call.args[0] if call.args else call.kwargs.get("message")
        types.append(type(message).__name__)
    return types


@pytest.mark.django_db
class TestBroadcastIsolation:
    """A failing broadcast must not abort the incident-channel publications."""

    @staticmethod
    def test_key_events_form_sent_when_broadcast_fails(mocker: MockerFixture) -> None:
        """The Key Events form still reaches the incident channel on broadcast failure."""
        incident, user = _mitigating_incident()
        _neutralise_channel_maintenance(mocker)
        mock_send = mocker.patch.object(Conversation, "send_message_and_save")
        mocker.patch(
            BROADCAST_TARGET,
            side_effect=SlackApiError("channel_not_found", response={"error": "channel_not_found"}),
        )

        incident.create_incident_update(created_by=user, status=IncidentStatus.MITIGATED)

        assert "SlackMessageKeyEvents" in _sent_message_types(mock_send)

    @staticmethod
    def test_broadcast_failure_is_logged(
        mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A swallowed broadcast failure stays observable in the logs."""
        incident, user = _mitigating_incident()
        _neutralise_channel_maintenance(mocker)
        mocker.patch.object(Conversation, "send_message_and_save")
        mocker.patch(
            BROADCAST_TARGET,
            side_effect=SlackApiError("channel_not_found", response={"error": "channel_not_found"}),
        )

        with caplog.at_level(logging.ERROR):
            incident.create_incident_update(
                created_by=user, status=IncidentStatus.MITIGATED
            )

        assert any(
            "incident_updated_broadcast_handler" in record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.ERROR
        ), "the broadcast failure must be logged, naming the receiver that failed"

    @staticmethod
    def test_broadcast_attempted_when_incident_channel_fails(
        mocker: MockerFixture,
    ) -> None:
        """Isolation works both ways: a dead incident channel must not mute broadcasts."""
        incident, user = _mitigating_incident()
        _neutralise_channel_maintenance(mocker)
        mocker.patch.object(Conversation, "send_message_and_save")
        mocker.patch(
            INCIDENT_CHANNEL_TARGET,
            side_effect=SlackApiError("channel_not_found", response={"error": "channel_not_found"}),
        )
        mock_broadcast = mocker.patch(BROADCAST_TARGET)

        incident.create_incident_update(created_by=user, status=IncidentStatus.MITIGATED)

        mock_broadcast.assert_called_once()
