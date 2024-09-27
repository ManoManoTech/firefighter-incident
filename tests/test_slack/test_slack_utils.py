from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.slack.utils import respond


@pytest.fixture
def mock_slack_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def body_channel() -> dict[str, str]:
    return {
        "channel_id": "C12345",
        "user_id": "U12345",
    }


@pytest.fixture
def body_dm() -> dict[str, str]:
    return {"channel_name": "directmessage", "user_id": "U12345"}


@pytest.fixture
def body_no_user_id() -> dict[str, str | dict[str, str]]:
    return {"channel_id": "C12345", "user": {"id": "U12345"}}


@pytest.fixture
def body_no_channel_id() -> dict[str, str | dict[str, str]]:
    return {"channel": {"id": "C12345"}, "user_id": "U12345"}


@pytest.fixture
def body_view_submission() -> dict[str, str]:
    return {"type": "view_submission", "channel_id": "C12345", "user_id": "U12345"}


def test_respond_direct_message(mock_slack_client: MagicMock, body_dm: dict[str, str]):
    respond(body_dm, "test message", client=mock_slack_client)
    mock_slack_client.chat_postMessage.assert_called_once_with(
        channel="U12345", text="test message", blocks=None
    )


def test_respond_channel(mock_slack_client: MagicMock, body_channel: dict[str, str]):
    respond(body_channel, "test message", client=mock_slack_client)
    mock_slack_client.chat_postEphemeral.assert_called_once_with(
        user="U12345", channel="C12345", text="test message", blocks=None
    )


def test_respond_channel_fallback_to_dm(
    mock_slack_client: MagicMock, body_channel: dict[str, str]
):
    mock_slack_client.chat_postEphemeral.side_effect = SlackApiError(
        "error", MagicMock()
    )
    respond(body_channel, "test message", client=mock_slack_client)

    expected_calls = [
        call(
            channel="U12345",
            text=":warning: The bot could not respond in the channel you invoked it. Please add it to this channel or conversation if you want to interact with the bot there. If you believe this is a bug, please tell @pulse.",
        ),
        call(channel="U12345", text="test message", blocks=None),
    ]
    mock_slack_client.chat_postMessage.assert_has_calls(expected_calls)


@pytest.mark.parametrize("channel_name", ["directmessage", "channel"])
def test_respond_directmessage_and_channel(
    mock_slack_client: MagicMock,
    body_dm: dict[str, Any],
    body_channel: dict[str, Any],
    channel_name: str,
):
    body = body_dm if channel_name == "directmessage" else body_channel

    respond(body, "test message", client=mock_slack_client)

    if channel_name == "directmessage":
        mock_slack_client.chat_postMessage.assert_called_with(
            channel="U12345", text="test message", blocks=None
        )
    else:
        mock_slack_client.chat_postEphemeral.assert_called_with(
            user="U12345", channel="C12345", text="test message", blocks=None
        )


def test_respond_no_channel_id(
    mock_slack_client: MagicMock, body_no_channel_id: dict[str, Any]
):
    respond(body_no_channel_id, "test message", client=mock_slack_client)

    mock_slack_client.chat_postEphemeral.assert_called_with(
        user="U12345", channel="C12345", text="test message", blocks=None
    )


def test_respond_view_submission(
    mock_slack_client: MagicMock, body_view_submission: dict[str, Any]
):
    mock_slack_client.chat_postEphemeral.side_effect = SlackApiError(
        "error", MagicMock()
    )
    respond(body_view_submission, "test message", client=mock_slack_client)

    mock_slack_client.chat_postMessage.assert_called_once_with(
        channel="U12345", text="test message", blocks=None
    )


def test_no_user_id_no_channel_id(mock_slack_client: MagicMock):
    with pytest.raises(
        ValueError,
        match="At least one is required",
    ):
        respond({}, "test message", client=mock_slack_client)
