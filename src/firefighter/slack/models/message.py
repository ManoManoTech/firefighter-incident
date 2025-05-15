from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models import IncidentUpdate
from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import DefaultWebClient, SlackApp, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient
    from slack_sdk.web.slack_response import SlackResponse

logger = logging.getLogger(__name__)


class MessageManager(models.Manager["Message"]):
    def get_or_none(self, **kwargs: Any) -> Message | None:
        try:
            return self.get(**kwargs)
        except Message.DoesNotExist:
            return None

    def create_from_slack_response(
        self, response: SlackResponse, **kwargs: Any
    ) -> Message | None:
        msg_res = response["message"]
        if msg_res is None:
            raise ValueError("msg_res is None")
        user = SlackUser.objects.get_user_by_slack_id(slack_id=msg_res["user"])
        if user is None:
            logger.warning(f"User not found for slack_id {msg_res['user']}")
            return None
        if not hasattr(user, "slack_user") or user.slack_user is None:
            logger.warning(f"User {user.id} has no slack_user")
            return None

        conversation = Conversation.objects.get(channel_id=response["channel"])
        ts = datetime.fromtimestamp(float(msg_res["ts"]), tz=UTC)
        return self.create(
            conversation=conversation,
            ts=ts,
            type=msg_res["type"],
            blocks=msg_res["blocks"],
            user=user.slack_user,
            text=msg_res["text"],
            **kwargs,
        )


class Message(models.Model):
    """Model a Slack API Conversation.
    A Slack Conversation can be a public channel, a private channel, a direct message, or a multi-person direct message.
    Reference: https://api.slack.com/types/conversation.
    """

    objects: MessageManager = MessageManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Conversation ID + Timestamp is the True composite PK (unsupported by Django)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, db_index=True
    )
    ts = models.DateTimeField(
        primary_key=False, help_text="UTC Timestamp of the message"
    )

    user = models.ForeignKey(SlackUser, on_delete=models.CASCADE)

    thread_ts = models.DateTimeField(null=True, blank=True)

    type = models.CharField(max_length=80)
    subtype = models.CharField(max_length=80, blank=True)

    text = models.TextField(max_length=40000, blank=True)
    blocks = models.JSONField(null=True, blank=True)

    incident_update = models.ForeignKey(
        IncidentUpdate,
        on_delete=models.CASCADE,
        related_name="slack_message",
        null=True,
    )

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="slack_message",
        null=True,
    )

    ff_type = models.CharField(max_length=64, blank=True)
    if TYPE_CHECKING:
        user_id: uuid.UUID | None
        conversation_id: uuid.UUID

    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(
                fields=["ts", "conversation"], name="message_ts_unicity"
            )
        ]

    def __str__(self) -> str:
        return f"{self.ts}@{self.conversation.name}: {self.text} {self!r}"

    def __repr__(self) -> str:
        return f"{self.ts}@{self.conversation_id}: {self.text}"

    def get_absolute_url(self) -> str:
        return self.get_permalink

    @property
    def get_permalink(self) -> str:
        return f"{SlackApp().details['url']}archives/{self.conversation.channel_id}/p{str(self.ts.timestamp()).replace('.', '')}"

    @slack_client
    def delete_self_and_slack(self, client: WebClient = DefaultWebClient) -> None:
        channel_id = self.conversation.channel_id
        if channel_id is None:
            raise ValueError("channel_id is None. Cannot delete message.")
        try:
            res = client.chat_delete(channel=channel_id, ts=str(self.ts.timestamp()))
            if res.get("ok"):
                self.delete()
            else:
                logger.warning(f"Failed to delete message {self} from Slack: {res}")
        except SlackApiError as e:
            logger.warning(f"Failed to delete message {self} from Slack: {e}")
