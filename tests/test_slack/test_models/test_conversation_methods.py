"""Tests for the Conversation manager and the Conversation helpers that talk to the Slack API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from firefighter.slack.factories import (
    MessageFactory,
    SlackConversationFactory,
    SlackUserFactory,
)
from firefighter.slack.messages.base import SlackMessageStrategy, SlackMessageSurface
from firefighter.slack.models.conversation import (
    Conversation,
    ConversationStatus,
    ConversationType,
)
from firefighter.slack.models.message import Message
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import SlackApp

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

BOT_SLACK_ID = "UBOT000001"
MESSAGE_TS = "1690000000.000100"


class _TestMessage(SlackMessageSurface):
    id = "ff_test_message"

    def get_text(self) -> str:
        return "Hello from the tests"


def _channel_payload(**flags: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "channel": {"id": "C0IMPORTED", "name": "imported-channel", **flags},
    }


def _posted_message_response(
    conversation: Conversation, *, ok: bool = True, ts: str = MESSAGE_TS
) -> dict[str, Any]:
    return {
        "ok": ok,
        "error": None if ok else "channel_not_found",
        "channel": conversation.channel_id,
        "ts": ts,
        "message": {
            "user": BOT_SLACK_ID,
            "ts": ts,
            "type": "message",
            "blocks": [],
            "text": "Hello from the tests",
        },
    }


@pytest.fixture
def public_conversation() -> Conversation:
    conversation = SlackConversationFactory.create(
        _type=ConversationType.PUBLIC_CHANNEL, _status=ConversationStatus.OPENED
    )
    # Messages posted by the app are stored with the bot as author
    SlackUserFactory.create(slack_id=BOT_SLACK_ID)
    return conversation


@pytest.mark.parametrize(
    ("flags", "expected_type", "expected_status"),
    [
        ({"is_channel": True, "is_private": False}, ConversationType.PUBLIC_CHANNEL, ConversationStatus.OPENED),
        ({"is_channel": True, "is_private": True}, ConversationType.PRIVATE_CHANNEL, ConversationStatus.OPENED),
        ({"is_group": True, "is_private": True}, ConversationType.PRIVATE_CHANNEL, ConversationStatus.OPENED),
        ({"is_im": True, "is_private": True}, ConversationType.DM, ConversationStatus.OPENED),
        ({"is_mpim": True, "is_private": True}, ConversationType.GROUP_DM, ConversationStatus.OPENED),
        ({"is_im": True, "is_private": False}, ConversationType.UNKNOWN, ConversationStatus.OPENED),
        ({"is_channel": True, "is_archived": True}, ConversationType.PUBLIC_CHANNEL, ConversationStatus.ARCHIVED),
    ],
)
def test_parse_slack_response(
    flags: dict[str, bool],
    expected_type: ConversationType,
    expected_status: ConversationStatus,
) -> None:
    channel_id, channel_name, channel_type, status = (
        Conversation.objects.parse_slack_response(_channel_payload(**flags))
    )

    assert channel_id == "C0IMPORTED"
    assert channel_name == "imported-channel"
    assert channel_type == expected_type
    assert status == expected_status


@pytest.mark.django_db
def test_links_point_to_the_channel(public_conversation: Conversation) -> None:
    team_id = SlackApp().details["team_id"]

    assert public_conversation.link == (
        f"https://slack.com/app_redirect?channel={public_conversation.channel_id}&team={team_id}"
    )
    assert public_conversation.deep_link == (
        f"slack://channel?id={public_conversation.channel_id}&team={team_id}"
    )


@pytest.mark.django_db
class TestSendMessage:
    @staticmethod
    def test_posts_in_the_conversation(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)

        public_conversation.send_message(text="Hi", client=client)

        client.chat_postMessage.assert_called_once_with(
            channel=public_conversation.channel_id, text="Hi", blocks=None
        )

    @staticmethod
    def test_refuses_another_channel(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)

        with pytest.raises(ValueError, match="can't set the channel"):
            public_conversation.send_message(text="Hi", channel="C0OTHER", client=client)
        client.chat_postMessage.assert_not_called()

    @staticmethod
    @pytest.mark.parametrize("pass_slack_user", [True, False])
    def test_ephemeral_message_targets_the_user(
        public_conversation: Conversation, *, pass_slack_user: bool
    ) -> None:
        client = MagicMock(spec=WebClient)
        slack_user: SlackUser = SlackUserFactory.create()
        user: SlackUser | str = slack_user if pass_slack_user else slack_user.slack_id

        public_conversation.send_message_ephemeral(_TestMessage(), user, client=client)

        kwargs = client.chat_postEphemeral.call_args.kwargs
        assert kwargs["user"] == slack_user.slack_id
        assert kwargs["channel"] == public_conversation.channel_id
        assert kwargs["text"] == "Hello from the tests"


@pytest.mark.django_db
class TestSendMessageAndSaveStrategies:
    @staticmethod
    def test_append_saves_the_message(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )

        public_conversation.send_message_and_save(_TestMessage(), client=client)

        saved = Message.objects.get(conversation=public_conversation)
        assert saved.ff_type == "ff_test_message"
        assert saved.ts == datetime.fromtimestamp(float(MESSAGE_TS), tz=UTC)

    @staticmethod
    def test_append_raises_when_slack_refuses(
        public_conversation: Conversation,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation, ok=False
        )

        with pytest.raises(SlackApiError):
            public_conversation.send_message_and_save(_TestMessage(), client=client)
        assert not Message.objects.filter(conversation=public_conversation).exists()

    @staticmethod
    def test_update_without_previous_message_appends(
        public_conversation: Conversation,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )

        public_conversation.send_message_and_save(
            _TestMessage(), client=client, strategy=SlackMessageStrategy.UPDATE
        )

        client.chat_update.assert_not_called()
        client.chat_postMessage.assert_called_once()
        assert Message.objects.filter(conversation=public_conversation).count() == 1

    @staticmethod
    def test_update_edits_the_last_message_of_the_same_type(
        public_conversation: Conversation,
    ) -> None:
        client = MagicMock(spec=WebClient)
        old = MessageFactory.create(
            conversation=public_conversation, ff_type="ff_test_message"
        )

        public_conversation.send_message_and_save(
            _TestMessage(), client=client, strategy=SlackMessageStrategy.UPDATE
        )

        client.chat_postMessage.assert_not_called()
        kwargs = client.chat_update.call_args.kwargs
        assert kwargs["channel"] == public_conversation.channel_id
        assert kwargs["ts"] == str(old.ts.timestamp())

    @staticmethod
    def test_replace_without_previous_message_saves_the_new_one(
        public_conversation: Conversation,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )

        public_conversation.send_message_and_save(
            _TestMessage(), client=client, strategy=SlackMessageStrategy.REPLACE
        )

        client.chat_delete.assert_not_called()
        assert Message.objects.filter(conversation=public_conversation).count() == 1

    @staticmethod
    @pytest.mark.parametrize(
        ("old_type", "strategy_args"),
        [
            ("ff_test_message", None),
            ("ff_older_type", {"replace": ["ff_older_type"]}),
        ],
    )
    def test_replace_deletes_the_previous_message(
        public_conversation: Conversation,
        mocker: MockerFixture,
        old_type: str,
        strategy_args: dict[str, Any] | None,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )
        old = MessageFactory.create(conversation=public_conversation, ff_type=old_type)
        delete = mocker.patch.object(Message, "delete_self_and_slack", autospec=True)

        public_conversation.send_message_and_save(
            _TestMessage(),
            client=client,
            strategy=SlackMessageStrategy.REPLACE,
            strategy_args=strategy_args,
        )

        delete.assert_called_once()
        # The factory sets a str id while the DB returns a UUID: compare them as strings
        assert str(delete.call_args.args[0].pk) == str(old.pk)
        new_message = Message.objects.exclude(id=old.id).get(
            conversation=public_conversation
        )
        assert new_message.ff_type == "ff_test_message"

    @staticmethod
    def test_replace_raises_when_slack_refuses(
        public_conversation: Conversation,
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation, ok=False
        )

        with pytest.raises(SlackApiError):
            public_conversation.send_message_and_save(
                _TestMessage(), client=client, strategy=SlackMessageStrategy.REPLACE
            )


@pytest.mark.django_db
class TestPinMessage:
    @staticmethod
    def test_pins_the_sent_message(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )
        client.pins_add.return_value = {"ok": True}

        public_conversation.send_message_and_save(_TestMessage(), client=client, pin=True)

        client.pins_add.assert_called_once_with(
            channel=public_conversation.channel_id, timestamp=MESSAGE_TS
        )

    @staticmethod
    def test_warns_when_slack_refuses_to_pin(
        public_conversation: Conversation, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = MagicMock(spec=WebClient)
        client.chat_postMessage.return_value = _posted_message_response(
            public_conversation
        )
        client.pins_add.return_value = {"ok": False, "error": "too_many_pins"}

        public_conversation.send_message_and_save(_TestMessage(), client=client, pin=True)

        assert "Could not pin a message! SlackResponse" in caplog.text

    @staticmethod
    def test_does_not_pin_a_message_without_ts(
        public_conversation: Conversation, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = MagicMock(spec=WebClient)

        client.chat_update.return_value = {"ok": True, "ts": ""}

        public_conversation.send_message_and_save(
            _TestMessage(),
            client=client,
            strategy=SlackMessageStrategy.UPDATE,
            strategy_args={"ts": MESSAGE_TS},
            pin=True,
        )

        client.pins_add.assert_not_called()
        assert "Has it been sent?" in caplog.text


@pytest.mark.django_db
class TestArchiveChannel:
    @staticmethod
    def test_archives_and_saves_the_status(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)
        client.conversations_archive.return_value = {"ok": True}

        assert public_conversation.archive_channel(client=client) is True

        public_conversation.refresh_from_db()
        assert public_conversation.status == ConversationStatus.ARCHIVED

    @staticmethod
    def test_api_error_returns_false(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)
        client.conversations_archive.side_effect = SlackApiError(
            "already_archived", response={"ok": False}
        )

        assert public_conversation.archive_channel(client=client) is False
        public_conversation.refresh_from_db()
        assert public_conversation.status == ConversationStatus.OPENED

    @staticmethod
    def test_not_ok_response_returns_false(public_conversation: Conversation) -> None:
        client = MagicMock(spec=WebClient)
        client.conversations_archive.return_value = {"ok": False}

        assert public_conversation.archive_channel(client=client) is False
        public_conversation.refresh_from_db()
        assert public_conversation.status == ConversationStatus.OPENED
