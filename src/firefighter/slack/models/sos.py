from __future__ import annotations

import uuid

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.user_group import UserGroup


class Sos(models.Model):
    """A SOS is a target with a name, a conversation, and optionally a user group.

    Incident responders can use it with `/incident sos` to ask for help to a specific group of people.

    Helpers will be notified in the selected conversation, and the user group will be mentioned (or `@here` if no user group is selected)
    """

    # XXX We need a relation to `Gear` or `Group` here, but current data is not good enough.
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    user_group = models.ForeignKey(
        UserGroup, blank=True, null=True, on_delete=models.CASCADE
    )
    conversation = models.ForeignKey(
        Conversation, blank=True, on_delete=models.CASCADE
    )

    class Meta(TypedModelMeta):
        verbose_name = "SOS"
        verbose_name_plural = "SOS"

    def __str__(self) -> str:
        return self.name

    @property
    def usergroup_slack_fmt(self) -> str:
        """Returns either `@usergroup` or `@here` depending on usergroup presence."""
        return f"@{self.user_group.handle}" if self.user_group else "@here"
