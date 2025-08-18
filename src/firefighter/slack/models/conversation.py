from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from django.db import models
from django.db.models import Q
from django.db.models.enums import IntegerChoices
from django_stubs_ext.db.models import TypedModelMeta
from slack_sdk.errors import SlackApiError

from firefighter.firefighter.utils import get_in
from firefighter.incidents.models import IncidentCategory, User
from firefighter.slack.messages.base import SlackMessageStrategy, SlackMessageSurface
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import DefaultWebClient, SlackApp, slack_client

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models.query import QuerySet
    from django_stubs_ext.db.models.manager import RelatedManager  # noqa: F401
    from slack_sdk.models.blocks.blocks import Block
    from slack_sdk.web.client import WebClient
    from slack_sdk.web.slack_response import SlackResponse

    from firefighter.slack.models.message import MessageManager


class ConversationStatus(IntegerChoices):
    NOT_OPENED = 0, "Not Opened"
    OPENED = 1, "Opened"
    ARCHIVED = 2, "Archived"


class ConversationType(IntegerChoices):
    UNKNOWN = 0, "Unknown"
    PUBLIC_CHANNEL = 10, "Public Channel"
    PRIVATE_CHANNEL = 20, "Private Channel"
    DM = 30, "DM"
    GROUP_DM = 40, "Group DM"


logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Conversation")


class ConversationManager(models.Manager[T], Generic[T]):
    def get_or_none(self, **kwargs: Any) -> Conversation | None:
        try:
            return self.get(**kwargs)
        except Conversation.DoesNotExist:
            return None

    def create_channel(
        self,
        name: str,
        *,
        is_private: bool = False,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> T | None:
        def attempt_creation(name: str, *, is_private: bool) -> SlackResponse | None:
            try:
                return client.conversations_create(name=name, is_private=is_private)
            except SlackApiError:
                logger.exception(
                    f"Could not create {'private ' if is_private else ''}channel with name: {name}."
                )
                return None

        slack_conv = attempt_creation(name, is_private=is_private)
        if slack_conv is None and is_private:
            logger.info(
                f"Retrying to create public Slack channel with name: {name} after failing to create as a private channel."
            )
            slack_conv = attempt_creation(name, is_private=False)

        if slack_conv is None or not slack_conv.get("ok"):
            logger.error(
                f"Could not create Slack channel with name: {name}, {slack_conv}"
            )
            return None

        (channel_id, channel_name, channel_type, status) = self.parse_slack_response(
            slack_conv=slack_conv
        )

        return self.create(
            name=channel_name,
            status=status,
            channel_id=channel_id,
            type=channel_type,
            **kwargs,
        )

    @slack_client
    def import_channel(
        self,
        slack_conversation_id: str,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> Conversation | None:
        try:
            slack_conv = client.conversations_info(channel=slack_conversation_id)
            logger.debug(f"Conversation fetched: {slack_conversation_id}, {slack_conv}")
        except SlackApiError:
            logger.exception(f"Could not fetch channel: {slack_conversation_id}.")
            return None

        if not slack_conv.get("ok"):
            return None

        (channel_id, channel_name, channel_type, status) = self.parse_slack_response(
            slack_conv=slack_conv
        )

        channel, _ = self.update_or_create(
            defaults={"channel_id": channel_id},
            name=channel_name,
            status=status,
            type=channel_type,
            **kwargs,
        )
        return channel

    @staticmethod
    def parse_slack_response(
        slack_conv: dict[str, Any] | SlackResponse,
    ) -> tuple[str, str, ConversationType, ConversationStatus]:
        status = (
            ConversationStatus.OPENED
            if not get_in(slack_conv, "channel.is_archived")
            else ConversationStatus.ARCHIVED
        )
        channel_name: str = get_in(slack_conv, "channel.name")
        channel_id: str = get_in(slack_conv, "channel.id")

        is_private = get_in(slack_conv, "channel.is_private")
        if get_in(slack_conv, "channel.is_channel") and not is_private:
            channel_type = ConversationType.PUBLIC_CHANNEL
        elif (
            get_in(slack_conv, "channel.is_group")
            or get_in(slack_conv, "channel.is_channel")
        ) and is_private:
            channel_type = ConversationType.PRIVATE_CHANNEL
        elif get_in(slack_conv, "channel.is_im") and is_private:
            channel_type = ConversationType.DM
        elif get_in(slack_conv, "channel.is_mpim") and is_private:
            channel_type = ConversationType.GROUP_DM
        else:
            channel_type = ConversationType.UNKNOWN
        return channel_id, channel_name, channel_type, status

    def not_incident_channel(self, query: QuerySet[T] | None = None) -> QuerySet[T]:
        qs = query or self.get_queryset().all()
        return qs.filter(incidentchannel__isnull=True)


class Conversation(models.Model):
    """Model a Slack API Conversation.
    A Slack Conversation can be a public channel, a private channel, a direct message, or a multi-person direct message.
    Reference: https://api.slack.com/types/conversation.
    """

    objects: ConversationManager[Conversation] = ConversationManager()  # type: ignore[assignment]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=80, blank=True)
    channel_id = models.CharField(max_length=128)
    _status = models.IntegerField(
        db_column="status",
        choices=ConversationStatus.choices,
        default=ConversationStatus.NOT_OPENED,
    )
    _type = models.IntegerField(
        db_column="type",
        choices=ConversationType.choices,
        default=ConversationType.UNKNOWN,
    )

    is_shared = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    members = models.ManyToManyField(User, blank=True)
    incident_categories = models.ManyToManyField["IncidentCategory", "IncidentCategory"](
        IncidentCategory, related_name="conversations", blank=True
    )
    tag = models.CharField(
        max_length=80,
        blank=True,
        help_text="Used by FireFighter internally to mark special conversations (#it-deploy, #tech-incidents...). Must be empty or unique.",
    )

    class Meta(TypedModelMeta):
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__type_valid",
                check=models.Q(_type__in=ConversationType.values),
            ),
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__status_valid",
                check=models.Q(_status__in=ConversationStatus.values),
            ),
            # Uniqueness constraint for tag if there is one
            models.UniqueConstraint(
                fields=["tag"], name="unique__tag", condition=~Q(tag="")
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.name} ({self.channel_id};{self.type.label};{self.status.label})"

    @property
    def status(self) -> ConversationStatus:
        return ConversationStatus(self._status)

    @status.setter
    def status(self, status: ConversationStatus) -> None:
        self._status = status

    @property
    def type(self) -> ConversationType:
        return ConversationType(self._type)

    @type.setter
    def type(self, type_: ConversationType) -> None:
        self._type = type_

    @property
    def link(self) -> str:
        """Regular HTTPS link to the conversation through Slack.com."""
        return f"https://slack.com/app_redirect?channel={self.channel_id}&team={SlackApp().details['team_id']}"

    @property
    def deep_link(self) -> str:
        """Deep link (`slack://`) to the conversation in the Slack client."""
        return (
            f"slack://channel?id={self.channel_id}&team={SlackApp().details['team_id']}"
        )

    @slack_client
    def send_message(
        self,
        text: str | None = None,
        blocks: Sequence[dict[str, Any] | Block] | None = None,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> None:
        """Convenience method to send a message on this conversation."""
        if kwargs.get("channel"):
            raise ValueError(
                "You can't set the channel when using send_message on a conversation!"
            )

        client.chat_postMessage(
            channel=self.channel_id, text=text, blocks=blocks, **kwargs
        )

    @slack_client
    def send_message_ephemeral(
        self,
        message: SlackMessageSurface,
        user: SlackUser | str,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> None:
        """Convenience method to send an ephemeral message on this conversation.
        `user`, `channel`, `blocks`, `text` and `metadata` should not be passed in kwargs.
        """
        user_id = user.slack_id if isinstance(user, SlackUser) else user

        client.chat_postEphemeral(
            user=user_id,
            channel=self.channel_id,
            **(kwargs | message.get_slack_message_params()),
        )

    @slack_client
    def send_message_and_save(
        self,
        message: SlackMessageSurface,
        client: WebClient = DefaultWebClient,
        strategy: SlackMessageStrategy | None = None,
        strategy_args: dict[str, Any] | None = None,
        *,
        pin: bool = False,
    ) -> SlackResponse:
        """Convenience method to send a message on this conversation."""
        if strategy is None:
            strategy = message.strategy

        kwargs = {}
        # XXX Get save context?
        if hasattr(message, "incident"):
            kwargs["incident"] = message.incident
        if hasattr(message, "incident_update"):
            kwargs["incident_update"] = message.incident_update
        kwargs["ff_type"] = message.id
        if strategy == SlackMessageStrategy.APPEND:
            strategy_res = self._send_message_strategy_append(message, client, kwargs)
        elif strategy == SlackMessageStrategy.UPDATE:
            strategy_res = self._send_message_strategy_update(message, client, kwargs)
        elif strategy == SlackMessageStrategy.REPLACE:
            strategy_res = self._send_message_strategy_replace(
                message, client, strategy_args, kwargs
            )
        if pin:
            self._pin_message(
                res=strategy_res,
                client=client,
            )
        return strategy_res

    def _send_message_strategy_replace(
        self,
        message: SlackMessageSurface,
        client: WebClient,
        strategy_args: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> SlackResponse:
        res = client.chat_postMessage(
            channel=self.channel_id, **message.get_slack_message_params()
        )
        if not res.get("ok"):
            raise SlackApiError(str(res.get("error")), res)
        if strategy_args is not None and strategy_args.get("replace") is not None:
            old_message = (
                self._get_message_manager()
                .filter(ff_type__in=strategy_args.get("replace"), conversation=self)
                .order_by("-ts")
                .first()
            )
        else:
            old_message = (
                self._get_message_manager()
                .filter(ff_type=message.id, conversation=self)
                .order_by("-ts")
                .first()
            )
        if old_message is None:
            # Fallback to append strategy
            self._get_message_manager().create_from_slack_response(res, **kwargs)

        else:
            old_message.delete_self_and_slack()
            self._get_message_manager().create_from_slack_response(res, **kwargs)
        return res

    def _send_message_strategy_update(
        self, message: SlackMessageSurface, client: WebClient, kwargs: dict[str, Any]
    ) -> SlackResponse:
        old_message = (
            self._get_message_manager()
            .filter(ff_type=message.id, conversation=self)
            .order_by("-ts")
            .first()
        )
        if old_message is None:
            # Fallback to append strategy
            return self._send_message_strategy_append(message, client, kwargs)

        return client.chat_update(
            channel=old_message.conversation.channel_id,
            ts=str(old_message.ts.timestamp()),
            **message.get_slack_message_params(),
        )

    def _send_message_strategy_append(
        self, message: SlackMessageSurface, client: WebClient, kwargs: dict[str, Any]
    ) -> SlackResponse:
        res = client.chat_postMessage(
            channel=self.channel_id, **message.get_slack_message_params()
        )
        if not res.get("ok"):
            raise SlackApiError(str(res.get("error")), res)
        self._get_message_manager().create_from_slack_response(res, **kwargs)
        return res

    def _pin_message(
        self, res: SlackResponse, client: WebClient = DefaultWebClient
    ) -> None:
        """Pin a message from the response of send_message_and_save."""
        if not (res["ok"] and res["ts"]):
            logger.warning(
                f"Could not pin a message! Has it been sent? SlackResponse: {res}"
            )
            return
        pin_response = client.pins_add(channel=self.channel_id, timestamp=res["ts"])
        if not pin_response["ok"]:
            logger.warning(
                f"Could not pin a message! SlackResponse: {pin_response}; Message: {res}"
            )

    @slack_client
    def add_bookmark(
        self,
        title: str,
        _type: str = "link",
        emoji: str | None = None,
        entity_id: str | None = None,
        link: str | None = None,  # include when type is 'link'
        parent_id: str | None = None,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> None:
        """Convenience method to add a bookmark on this conversation."""
        client.bookmarks_add(
            channel_id=self.channel_id,
            title=title,
            link=link,
            emoji=emoji,
            type=_type,
            entity_id=entity_id,
            parent_id=parent_id,
            **kwargs,
        )

    @slack_client
    def conversations_join(self, client: WebClient = DefaultWebClient) -> SlackResponse:
        return client.conversations_join(channel=self.channel_id)

    @slack_client
    def update_topic(
        self, topic: str, client: WebClient = DefaultWebClient
    ) -> SlackResponse:
        return client.conversations_setTopic(channel=self.channel_id, topic=topic)

    @staticmethod
    def _get_message_manager() -> MessageManager:
        # ruff: noqa: PLC0415
        from firefighter.slack.models.message import Message

        return Message.objects

    @slack_client
    def archive_channel(self, client: WebClient = DefaultWebClient) -> bool:
        try:
            response = client.conversations_archive(channel=self.channel_id)
            logger.debug(response)

        except SlackApiError:
            logger.warning(
                f"Could not archive channel {self.channel_id} due to an API error",
                exc_info=True,
            )

            return False

        if response.get("ok"):
            self.status = ConversationStatus.ARCHIVED
            self.save()
            return True
        logger.warning(f"Could not archive channel {self.channel_id}: {response}")

        return False
