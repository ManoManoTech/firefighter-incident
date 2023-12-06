from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as BaseUserManager
from django.db import models
from django.urls import reverse
from django_stubs_ext.db.models import TypedModelMeta

if TYPE_CHECKING:
    from django.apps import apps
    from django_stubs_ext.db.models.manager import RelatedManager

    from firefighter.incidents.models.incident import IncidentRole

    if apps.is_installed("firefighter.slack"):
        from firefighter.slack.models.user import SlackUser
    if apps.is_installed("firefighter.pagerduty"):
        from firefighter.pagerduty.models import PagerDutyUser
    if apps.is_installed("firefighter.jira_app"):
        from firefighter.jira_app.models import JiraUser


logger = logging.getLogger(__name__)


class UserManager(BaseUserManager["User"]):
    def get_or_none(self, **kwargs: Any) -> User | None:
        try:
            return self.get(**kwargs)
        except User.DoesNotExist:
            return None


class User(AbstractUser):
    objects: ClassVar[UserManager] = UserManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=128,
        help_text="User fullname. Prefer to set `first_name` and `last_name`, and get `full_name`. ",
    )
    email = models.EmailField(max_length=128, unique=True)
    bot = models.BooleanField(
        default=False,
        help_text="Used for non-person accounts (e.g. integrations that have bot/shared accounts.",
    )

    avatar = models.URLField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="URL to user avatar. Can be hosted externally.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        ordering = ["username"]

    def __str__(self) -> str:
        return self.full_name

    @property
    @admin.display(ordering="first_name")
    def full_name(self) -> str:
        """User full name (first + last name). Looks for the first_name and last_name fields, then name, then username. Will return an empty string if none of these are set."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.name:
            return self.name
        if self.username:
            return self.username
        return ""

    def get_absolute_url(self) -> str:
        return reverse("incidents:user-detail", kwargs={"user_id": self.id})

    if TYPE_CHECKING:
        roles_set: RelatedManager[IncidentRole]
        if apps.is_installed("firefighter.slack"):
            slack_user: SlackUser | None
            slack_user_id: uuid.UUID | None
        if apps.is_installed("firefighter.pagerduty"):
            pagerduty_user: PagerDutyUser | None
            pagerduty_user_id: uuid.UUID | None
        if apps.is_installed("firefighter.raid"):
            jira_user: JiraUser | None
            jira_user_id: str | None
