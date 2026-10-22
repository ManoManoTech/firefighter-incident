"""Archiving an incident channel outside the closing process is reported."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.slack.factories import (
    IncidentChannelFactory,
    SlackConversationFactory,
    SlackUserFactory,
)
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentChannelArchivedAlert,
    SlackMessageIncidentChannelArchivedDM,
)
from firefighter.slack.models.conversation import ConversationStatus
from firefighter.slack.tasks.notify_out_of_process_archive import (
    notify_out_of_process_archive,
)
from firefighter.slack.views.events.channel_archive import channel_archive

BOT_ID = "UBOT"
HUMAN_ID = "UHUMAN"


@pytest.fixture(autouse=True)
def bot_identity():
    slack_app = MagicMock()
    slack_app.details = {"user_id": BOT_ID}
    with patch(
        "firefighter.slack.views.events.channel_archive.SlackApp", return_value=slack_app
    ):
        yield


@pytest.fixture
def mock_notify():
    with patch(
        "firefighter.slack.tasks.notify_out_of_process_archive.notify_out_of_process_archive"
    ) as mocked:
        yield mocked


def _incident_channel(status: int = IncidentStatus.INVESTIGATING.value):
    return IncidentChannelFactory.create(incident=IncidentFactory.create(_status=status))


@pytest.mark.django_db
class TestChannelArchiveEvent:
    @pytest.mark.usefixtures("mock_notify")
    def test_marks_the_conversation_archived(self):
        channel = _incident_channel()

        channel_archive({"channel": channel.channel_id, "user": HUMAN_ID})

        channel.refresh_from_db()
        assert channel.status == ConversationStatus.ARCHIVED

    def test_reports_an_archive_by_someone_on_an_open_incident(self, mock_notify):
        channel = _incident_channel()

        channel_archive({"channel": channel.channel_id, "user": HUMAN_ID})

        mock_notify.delay.assert_called_once_with(channel.incident.id, HUMAN_ID)

    def test_ignores_the_bot_archiving_on_closure(self, mock_notify):
        channel = _incident_channel()

        channel_archive({"channel": channel.channel_id, "user": BOT_ID})

        mock_notify.delay.assert_not_called()

    def test_ignores_a_closed_incident(self, mock_notify):
        channel = _incident_channel(status=IncidentStatus.CLOSED.value)

        channel_archive({"channel": channel.channel_id, "user": HUMAN_ID})

        mock_notify.delay.assert_not_called()

    def test_ignores_a_channel_that_is_not_an_incident_channel(self, mock_notify):
        conversation = SlackConversationFactory.create()

        channel_archive({"channel": conversation.channel_id, "user": HUMAN_ID})

        mock_notify.delay.assert_not_called()

    def test_ignores_an_event_without_a_channel(self, mock_notify):
        channel_archive({"user": HUMAN_ID})

        mock_notify.delay.assert_not_called()


@pytest.fixture
def mock_send():
    with patch(
        "firefighter.slack.models.conversation.Conversation.send_message_and_save"
    ) as mocked:
        yield mocked


@pytest.fixture
def mock_dm():
    with patch(
        "firefighter.slack.models.user.SlackUser.send_private_message"
    ) as mocked:
        yield mocked


@pytest.mark.django_db
class TestNotifyOutOfProcessArchive:
    def test_alerts_the_support_channel_and_dms_the_archiver(self, mock_send, mock_dm):
        SlackConversationFactory.create(tag="dev_firefighter")
        incident = _incident_channel().incident
        SlackUserFactory.create(user=UserFactory.create(), slack_id=HUMAN_ID)

        notify_out_of_process_archive(incident.id, HUMAN_ID)

        (alert,), _ = mock_send.call_args
        assert isinstance(alert, SlackMessageIncidentChannelArchivedAlert)
        assert HUMAN_ID in alert.get_text()
        (dm,), _ = mock_dm.call_args
        assert isinstance(dm, SlackMessageIncidentChannelArchivedDM)
        assert f"#{incident.id}" in dm.get_text()

    def test_still_alerts_when_the_archiver_is_unknown(self, mock_send, mock_dm):
        SlackConversationFactory.create(tag="dev_firefighter")
        incident = _incident_channel().incident

        notify_out_of_process_archive(incident.id, HUMAN_ID)

        mock_send.assert_called_once()
        mock_dm.assert_not_called()

    def test_still_dms_without_a_support_channel(self, mock_send, mock_dm):
        incident = _incident_channel().incident
        SlackUserFactory.create(user=UserFactory.create(), slack_id=HUMAN_ID)

        notify_out_of_process_archive(incident.id, HUMAN_ID)

        mock_send.assert_not_called()
        mock_dm.assert_called_once()

    def test_slack_failures_do_not_fail_the_task(self, mock_send, mock_dm):
        SlackConversationFactory.create(tag="dev_firefighter")
        incident = _incident_channel().incident
        SlackUserFactory.create(user=UserFactory.create(), slack_id=HUMAN_ID)
        mock_send.side_effect = SlackApiError("not_in_channel", {"ok": False})
        mock_dm.side_effect = SlackApiError("cannot_dm", {"ok": False})

        notify_out_of_process_archive(incident.id, HUMAN_ID)

        mock_send.assert_called_once()
        mock_dm.assert_called_once()

    @pytest.mark.usefixtures("mock_send")
    def test_dms_turned_off_by_the_archiver_only_warn(self, mock_dm, caplog):
        SlackConversationFactory.create(tag="dev_firefighter")
        incident = _incident_channel().incident
        SlackUserFactory.create(user=UserFactory.create(), slack_id=HUMAN_ID)
        mock_dm.side_effect = SlackApiError(
            "messages_tab_disabled", {"ok": False, "error": "messages_tab_disabled"}
        )

        notify_out_of_process_archive(incident.id, HUMAN_ID)

        mock_dm.assert_called_once()
        assert "has disabled private messages from bots" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
