"""An incident whose channel is archived can still change, but nothing is written to the channel.

Slack refuses any write in an archived channel (`is_archived`), so every attempt logged an
ERROR and fired the application error monitor: e.g. when the Jira status sync reopened a
closed incident.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from slack_sdk.errors import SlackApiError

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
from firefighter.slack.signals.incident_updated import (
    incident_key_events_updated_handler,
)

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


@pytest.mark.django_db
class TestKeyEventsUpdateOnChannelArchivedMeanwhile:
    """The channel can be archived between the writable check and the Slack call.

    Typically: a timeline correction arms a deferred sync, then the incident is closed
    (which archives its channel) before the sync runs. Slack then answers `is_inactive`
    to `chat.update`, or `is_archived` to `chat.postMessage`.
    """

    @staticmethod
    def _send_fails_with(mocker: MockerFixture, slack_error: str) -> MagicMock:
        mocker.patch(
            "firefighter.slack.views.modals.key_event_message.SlackMessageKeyEvents"
        )
        return mocker.patch.object(
            Conversation,
            "send_message_and_save",
            side_effect=SlackApiError(slack_error, {"ok": False, "error": slack_error}),
        )

    @staticmethod
    @pytest.mark.parametrize("slack_error", ["is_inactive", "is_archived"])
    def test_records_the_archive_instead_of_failing(
        mocker: MockerFixture, slack_error: str
    ) -> None:
        incident = _incident(ConversationStatus.OPENED)
        send = TestKeyEventsUpdateOnChannelArchivedMeanwhile._send_fails_with(
            mocker, slack_error
        )

        incident_key_events_updated_handler(sender=__name__, incident=incident)

        send.assert_called_once()
        assert (
            Conversation.objects.get(pk=incident.conversation.pk).status
            == ConversationStatus.ARCHIVED
        )

    @staticmethod
    def test_other_slack_errors_still_raise(mocker: MockerFixture) -> None:
        incident = _incident(ConversationStatus.OPENED)
        TestKeyEventsUpdateOnChannelArchivedMeanwhile._send_fails_with(
            mocker, "ratelimited"
        )

        with pytest.raises(SlackApiError):
            incident_key_events_updated_handler(sender=__name__, incident=incident)

        assert (
            Conversation.objects.get(pk=incident.conversation.pk).status
            == ConversationStatus.OPENED
        )
