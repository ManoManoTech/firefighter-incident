"""Private incidents get a public channel and a notice asking a Slack admin to make it private.

Workspaces commonly restrict private channel creation to Slack admins, and an app cannot be
granted admin rights: `conversations.create(is_private=True)` then fails with
`restricted_action`. The app no longer tries, and posts a notice instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from firefighter.incidents.factories import IncidentCategoryFactory, IncidentFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentChannelMustBePrivate,
    SlackMessageIncidentDeclaredAnnouncement,
)
from firefighter.slack.models.conversation import Conversation, ConversationType
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.signals.create_incident_conversation import (
    create_incident_slack_conversation,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models.incident import Incident


def _make_incident(*, private: bool) -> Incident:
    category = IncidentCategoryFactory.create(name="Exploited vulnerability", private=private)
    return IncidentFactory.create(incident_category=category, private=private)


def _created_channel_response(name: str) -> dict[str, object]:
    return {
        "ok": True,
        "channel": {
            "id": "C0NEWCHANNEL",
            "name": name,
            "is_channel": True,
            "is_group": False,
            "is_private": False,
            "is_archived": False,
        },
    }


@pytest.mark.django_db
class TestCreateChannel:
    @staticmethod
    def test_private_incident_channel_is_created_public() -> None:
        incident = _make_incident(private=True)
        client = MagicMock(spec=WebClient)
        client.conversations_create.return_value = _created_channel_response(
            "20261020-1-prd-exploited-vulnerability"
        )

        channel = IncidentChannel.objects.create_incident_channel(
            incident=incident, client=client
        )

        client.conversations_create.assert_called_once()
        assert "is_private" not in client.conversations_create.call_args.kwargs
        assert channel is not None
        assert channel.type == ConversationType.PUBLIC_CHANNEL
        assert channel.incident == incident

    @staticmethod
    def test_creation_failure_returns_none_without_retry(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.conversations_create.side_effect = SlackApiError(
            "name_taken", response={"ok": False, "error": "name_taken"}
        )

        channel = Conversation.objects.create_channel(name="taken-name", client=client)

        assert channel is None
        client.conversations_create.assert_called_once_with(name="taken-name")
        assert "Could not create channel with name: taken-name." in caplog.text

    @staticmethod
    def test_not_ok_response_returns_none() -> None:
        client = MagicMock(spec=WebClient)
        client.conversations_create.return_value = {"ok": False}

        assert Conversation.objects.create_channel(name="some-name", client=client) is None


@pytest.mark.django_db
class TestChannelMustBePrivateNotice:
    @staticmethod
    def _run_handler(mocker: MockerFixture, incident: Incident) -> MagicMock:
        new_channel = MagicMock()
        new_channel.channel_id = "C0NEWCHANNEL"
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.IncidentChannel.objects.create_incident_channel",
            return_value=new_channel,
        )
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.should_publish_in_general_channel",
            return_value=False,
        )
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.should_publish_in_it_deploy_channel",
            return_value=False,
        )
        # The handler invites through incident.conversation, which the mocked factory did not create
        mocker.patch.object(type(incident), "conversation", new_channel, create=True)

        create_incident_slack_conversation(incident=incident)
        return new_channel

    def test_private_incident_gets_pinned_notice(self, mocker: MockerFixture) -> None:
        incident = _make_incident(private=True)

        channel = self._run_handler(mocker, incident)

        channel.conversations_join.assert_called_once()
        sent = [
            (type(call.args[0]), call.kwargs)
            for call in channel.send_message_and_save.call_args_list
        ]
        assert (SlackMessageIncidentDeclaredAnnouncement, {"pin": True}) in sent
        assert (SlackMessageIncidentChannelMustBePrivate, {"pin": True}) in sent

    def test_public_incident_gets_no_notice(self, mocker: MockerFixture) -> None:
        incident = _make_incident(private=False)

        channel = self._run_handler(mocker, incident)

        channel.conversations_join.assert_called_once()
        sent_types = [
            type(call.args[0]) for call in channel.send_message_and_save.call_args_list
        ]
        assert SlackMessageIncidentChannelMustBePrivate not in sent_types


@pytest.mark.django_db
def test_notice_names_the_category_and_asks_for_an_admin() -> None:
    incident = _make_incident(private=True)

    message = SlackMessageIncidentChannelMustBePrivate(incident)

    assert "Exploited vulnerability" in message.get_text()
    blocks_text = message.get_blocks()[0].text.text
    assert "Exploited vulnerability" in blocks_text
    assert "A Slack admin must convert it to private" in blocks_text
