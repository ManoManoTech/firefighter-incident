"""An incident whose channel is archived can still change, but nothing is written to the channel.

Slack refuses any write in an archived channel (`is_archived`), so every attempt logged an
ERROR and fired the application error monitor: e.g. when the Jira status sync reopened a
closed incident.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.models.conversation import (
    Conversation,
    ConversationStatus,
    incident_has_writable_channel,
)
from firefighter.slack.models.incident_channel import IncidentChannel

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


def _incident(channel_status: ConversationStatus | None) -> Incident:
    incident = IncidentFactory.create(
        priority=Priority.objects.get(name="P3"),
        _status=IncidentStatus.MITIGATING,
    )
    if channel_status is not None:
        IncidentChannelFactory.create(incident=incident, _status=channel_status)
    return Incident.objects.get(pk=incident.pk)


def _mock_slack_writes(mocker: MockerFixture) -> dict[str, MagicMock]:
    return {
        "send_message_and_save": mocker.patch.object(
            Conversation, "send_message_and_save"
        ),
        "rename_if_needed": mocker.patch.object(IncidentChannel, "rename_if_needed"),
        "set_incident_channel_topic": mocker.patch.object(
            IncidentChannel, "set_incident_channel_topic"
        ),
        "invite_users": mocker.patch.object(IncidentChannel, "invite_users"),
    }


@pytest.mark.django_db
class TestIncidentHasWritableChannel:
    @staticmethod
    def test_no_channel() -> None:
        assert not incident_has_writable_channel(_incident(None))

    @staticmethod
    def test_open_channel() -> None:
        assert incident_has_writable_channel(_incident(ConversationStatus.OPENED))

    @staticmethod
    def test_archived_channel() -> None:
        assert not incident_has_writable_channel(_incident(ConversationStatus.ARCHIVED))


@pytest.mark.django_db
class TestStatusUpdateOnArchivedChannel:
    @staticmethod
    def test_nothing_is_written_to_an_archived_channel(mocker: MockerFixture) -> None:
        incident = _incident(ConversationStatus.ARCHIVED)
        writes = _mock_slack_writes(mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(), status=IncidentStatus.MITIGATED
        )

        assert incident.status == IncidentStatus.MITIGATED
        for name, mock in writes.items():
            assert not mock.called, f"{name} was called on an archived channel"

    @staticmethod
    def test_an_open_channel_is_still_updated(mocker: MockerFixture) -> None:
        """Contrast: the same update on an open channel publishes as before."""
        incident = _incident(ConversationStatus.OPENED)
        writes = _mock_slack_writes(mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(), status=IncidentStatus.MITIGATED
        )

        assert writes["send_message_and_save"].called
        assert writes["rename_if_needed"].called
