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
        return cast(str, self.random_element("UW")) + "".join(
            random.choices(  # noqa: S311
                string.ascii_uppercase + string.digits, k=self.random_int(8, 15)
            )
        )

    def slack_conversation_id(self) -> str:
        return cast(str, self.random_element("C")) + "".join(
            random.choices(  # noqa: S311
                string.ascii_uppercase + string.digits, k=self.random_int(8, 15)
            )
        )


Faker.add_provider(SlackProvider)


class SlackUserFactory(DjangoModelFactory):
    class Meta:
        model = SlackUser

    id = Faker("uuid4")
    slack_id = Faker("slack_user_id")
    user = SubFactory(UserFactory)
    username = Faker("user_name")
    image = Faker("image_url")


class SlackConversationFactory(DjangoModelFactory):
    class Meta:
        model = Conversation
        skip_postgeneration_save = True

    id = Faker("uuid4")
    name = Faker("name")
    channel_id = Faker("slack_conversation_id")
    _status = FuzzyChoice(ConversationStatus)
    _type = FuzzyChoice(ConversationType)
    is_shared = Faker("boolean")
    created_at = LazyFunction(timezone.now)
    updated_at = LazyFunction(timezone.now)
    members = RelatedFactory(UserFactory)
    tag = Faker("slug")


class IncidentChannelFactory(SlackConversationFactory):
    class Meta:
        model = IncidentChannel

    incident = SubFactory(IncidentFactory)


class MessageFactory(DjangoModelFactory):
    class Meta:
        model = Message

    id = Faker("uuid4")
    conversation = SubFactory(SlackConversationFactory)
    ts = LazyFunction(timezone.now)
    user = SubFactory(SlackUserFactory)
    thread_ts = Faker("past_datetime", tzinfo=timezone.get_current_timezone())
    type = Faker("word")
    subtype = Faker("word")
    text = Faker("text", max_nb_chars=40000)
    blocks: dict[Any, Any] = {}  # JSONField can be represented as a dictionary
    incident = SubFactory(IncidentFactory)
    ff_type = Faker("random_element", elements=[Faker("word"), ""])
