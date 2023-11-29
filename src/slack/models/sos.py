from __future__ import annotations

import uuid

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from slack.models.conversation import Conversation
from slack.models.user_group import UserGroup


class Sos(models.Model):
    """Sos model."""

    # XXX We need a relation to `Gear` or `Group` here, but current data is not good enough.
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    user_group = models.ForeignKey[UserGroup | None, UserGroup | None](
        UserGroup, blank=True, null=True, on_delete=models.CASCADE
    )
    conversation = models.ForeignKey[Conversation, Conversation](
        Conversation, blank=True, on_delete=models.CASCADE
    )

    @property
    def usergroup_slack_fmt(self) -> str:
        """Returns either `@usergroup` or `@here` depending on usergroup presence."""
        return f"@{self.user_group.handle}" if self.user_group else "@here"

    class Meta(TypedModelMeta):
        verbose_name = "SOS"
        verbose_name_plural = "SOS"

    def __str__(self) -> str:
        return self.name
