from __future__ import annotations

import pytest

from firefighter.slack.models.conversation import Conversation
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
