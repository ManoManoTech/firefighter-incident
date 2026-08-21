from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from firefighter.incidents.factories import IncidentFactory
from firefighter.slack.messages.base import SlackMessageStrategy
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.views.modals.review_timeline import SlackMessageReviewTimeline
from tests.test_slack.conftest import MockWebClient


@pytest.mark.django_db
def test_update_topic(
    conversation: Conversation, mock_web_client: MockWebClient
) -> None:
    mock_web_client.conversations_setTopic.return_value = {"ok": True}

    conversation.update_topic("New Topic", client=mock_web_client)
    assert mock_web_client.conversations_setTopic.called


@pytest.mark.django_db
def test_conversations_join(
    conversation: Conversation, mock_web_client: MockWebClient
) -> None:
    mock_web_client.conversations_join.return_value = {"ok": True}

    conversation.conversations_join(client=mock_web_client)
    assert mock_web_client.conversations_join.called


@pytest.mark.django_db
def test_send_message_update_strategy_targets_explicit_message_when_given(
    conversation: Conversation, mock_web_client: MockWebClient
) -> None:
    """`strategy_args={"ts": ...}` must update that exact message directly.

    Without it, the UPDATE strategy looks up "the last message of this
    ff_type" in the DB - not what's wanted when a caller already knows
    precisely which message it's resolving (e.g. from a button-click
    payload), since more than one message of the same type can coexist.
    """
    mock_web_client.chat_update = MagicMock(return_value={"ok": True})
    incident = IncidentFactory.create()
    message = SlackMessageReviewTimeline(incident, carry_over_payload="{}")

    conversation.send_message_and_save(
        message,
        client=mock_web_client,
        strategy=SlackMessageStrategy.UPDATE,
        strategy_args={"ts": "1690000000.123456", "channel_id": "C0TARGET"},
    )

    mock_web_client.chat_update.assert_called_once()
    _, kwargs = mock_web_client.chat_update.call_args
    assert kwargs["channel"] == "C0TARGET"
    assert kwargs["ts"] == "1690000000.123456"
