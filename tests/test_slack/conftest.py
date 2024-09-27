from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient

from firefighter.incidents.factories import UserFactory
from firefighter.incidents.models import Incident, User
from firefighter.slack.factories import (
    IncidentChannelFactory,
    SlackConversationFactory,
    SlackUserFactory,
)
from firefighter.slack.models import SlackUser
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.incident_channel import IncidentChannel

# XXX: Deduplicate from other fixtures


# Fixture to create a SlackUser instance
@pytest.fixture
def slack_user_saved() -> SlackUser:
    user = UserFactory.create()
    return SlackUserFactory.create(user=user)


@pytest.fixture
def conversation() -> Conversation:
    return SlackConversationFactory.create()


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def slack_user(user: User) -> SlackUser:
    return SlackUserFactory.create(user=user)


class MockWebClient(WebClient):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["token"] = "xoxb-1234-fake-token-test"  # noqa: S105
        kwargs["base_url"] = "https://fake-slack-web-client.localhost"
        super().__init__(*args, **kwargs)
        self.base_url = kwargs["base_url"]
        self.token = kwargs["token"]
        self.conversations_invite = MagicMock()  # type: ignore[method-assign]
        self.conversations_rename = MagicMock()  # type: ignore[method-assign]
        self.users_info = MagicMock()  # type: ignore[method-assign]
        self.conversations_setTopic = MagicMock()  # type: ignore[method-assign]
        self.conversations_join = MagicMock()  # type: ignore[method-assign]


@pytest.fixture
def mock_web_client() -> MockWebClient:
    return MockWebClient()


@pytest.fixture
def incident_channel(incident_saved: Incident) -> IncidentChannel:
    return IncidentChannelFactory.create(incident=incident_saved)
