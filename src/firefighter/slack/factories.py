from __future__ import annotations

import random
import string
from typing import Any

from django.utils import timezone
from factory import LazyFunction, RelatedFactory, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice
from faker import providers
from pyparsing import cast

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.slack.models import SlackUser
from firefighter.slack.models.conversation import (
    Conversation,
    ConversationStatus,
    ConversationType,
)
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.models.message import Message


class SlackProvider(providers.BaseProvider):
    """Custom Faker provider for generating Slack IDs."""

    def slack_user_id(self) -> str:
        return cast(str, self.random_element("UW")) + "".join(  # type: ignore[redundant-cast]
            random.choices(  # noqa: S311
                string.ascii_uppercase + string.digits, k=self.random_int(8, 15)
            )
        )

    def slack_conversation_id(self) -> str:
        return cast(str, self.random_element("C")) + "".join(  # type: ignore[redundant-cast]
            random.choices(  # noqa: S311
                string.ascii_uppercase + string.digits, k=self.random_int(8, 15)
            )
        )


Faker.add_provider(SlackProvider)  # type: ignore[no-untyped-call]


class SlackUserFactory(DjangoModelFactory[SlackUser]):
    class Meta:
        model = SlackUser

    id = Faker("uuid4")  # type: ignore[no-untyped-call]
    slack_id = Faker("slack_user_id")  # type: ignore[no-untyped-call]
    user = SubFactory(UserFactory)  # type: ignore[no-untyped-call]
    username = Faker("user_name")  # type: ignore[no-untyped-call]
    image = Faker("image_url")  # type: ignore[no-untyped-call]


class SlackConversationFactory(DjangoModelFactory[Conversation]):
    class Meta:
        model = Conversation
        skip_postgeneration_save = True

    id = Faker("uuid4")  # type: ignore[no-untyped-call]
    name = Faker("name")  # type: ignore[no-untyped-call]
    channel_id = Faker("slack_conversation_id")  # type: ignore[no-untyped-call]
    _status = FuzzyChoice(ConversationStatus)  # type: ignore[no-untyped-call]
    _type = FuzzyChoice(ConversationType)  # type: ignore[no-untyped-call]
    is_shared = Faker("boolean")  # type: ignore[no-untyped-call]
    created_at = LazyFunction(timezone.now)  # type: ignore[no-untyped-call]
    updated_at = LazyFunction(timezone.now)  # type: ignore[no-untyped-call]
    members = RelatedFactory(UserFactory)  # type: ignore[no-untyped-call]
    tag = Faker("slug")  # type: ignore[no-untyped-call]


class IncidentChannelFactory(SlackConversationFactory):
    class Meta:
        model = IncidentChannel

    incident = SubFactory(IncidentFactory)  # type: ignore[no-untyped-call]


class MessageFactory(DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = Message

    id = Faker("uuid4")  # type: ignore[no-untyped-call]
    conversation = SubFactory(SlackConversationFactory)  # type: ignore[no-untyped-call]
    ts = LazyFunction(timezone.now)  # type: ignore[no-untyped-call]
    user = SubFactory(SlackUserFactory)  # type: ignore[no-untyped-call]
    thread_ts = Faker("past_datetime", tzinfo=timezone.get_current_timezone())  # type: ignore[no-untyped-call]
    type = Faker("word")  # type: ignore[no-untyped-call]
    subtype = Faker("word")  # type: ignore[no-untyped-call]
    text = Faker("text", max_nb_chars=40000)  # type: ignore[no-untyped-call]
    blocks: dict[Any, Any] = {}  # JSONField can be represented as a dictionary
    incident = SubFactory(IncidentFactory)  # type: ignore[no-untyped-call]
    ff_type = Faker("random_element", elements=[Faker("word"), ""])  # type: ignore[no-untyped-call]
