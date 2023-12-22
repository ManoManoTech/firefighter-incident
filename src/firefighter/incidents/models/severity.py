from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import models
from django.db.models import Manager
from django_stubs_ext.db.models import TypedModelMeta


class Severity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    value = models.IntegerField(unique=True)
    emoji = models.CharField(max_length=5, default="🔥")
    description = models.CharField(max_length=128)
    order = models.IntegerField(default=0, unique=True)
    default = models.BooleanField(default=False)
    needs_postmortem = models.BooleanField(default=False)
    enabled_create = models.BooleanField(
        default=True, help_text="Can you create a new incident with this severity?"
    )
    enabled_update = models.BooleanField(
        default=True, help_text="Can you update an incident to this severity?"
    )
    reminder_time = models.DurationField(
        default=timedelta(hours=1),
        help_text="Time before an incident without any incident update will receive a reminder.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = Manager["Severity"]()

    class Meta(TypedModelMeta):
        ordering = ["order"]
        verbose_name_plural = "severities (legacy)"
        verbose_name = "severity (legacy)"
        constraints = [
            models.UniqueConstraint(
                fields=["default"],
                name="unique__default",
                condition=models.Q(default=True),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_default(cls) -> Severity:
        return Severity.objects.get(default=True)

    @property
    def full_name(self) -> str:
        return f"{self.emoji} {self.name} - {self.description}"
