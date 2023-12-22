from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import models
from django.db.models import Manager
from django_stubs_ext.db.models import TypedModelMeta


class Priority(models.Model):
    """A priority for an incident."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    value = models.IntegerField(unique=True)
    emoji = models.CharField(max_length=5, default="🔥")
    description = models.CharField(max_length=128)
    order = models.IntegerField(default=0, unique=True)
    default = models.BooleanField(default=False)
    needs_postmortem = models.BooleanField(default=False)
    enabled_create = models.BooleanField(
        default=True, help_text="Can you create a new incident with this priority?"
    )
    enabled_update = models.BooleanField(
        default=True, help_text="Can you update an incident to this priority?"
    )
    reminder_time = models.DurationField(
        default=timedelta(hours=1),
        help_text="Time before an incident without any incident update will receive a reminder.",
    )
    sla = models.DurationField(
        verbose_name="SLA",
        default=timedelta(hours=1),
        help_text="Service Level Agreement",
    )
    recommended_response_type = models.CharField(max_length=128, null=True, blank=True)
    # XXX Add choices to recommended_response_type

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = Manager["Priority"]()

    class Meta(TypedModelMeta):
        ordering = ["order"]
        verbose_name_plural = "priorities"
        constraints = [
            models.UniqueConstraint(
                fields=["default"],
                name="unique_priority_default",
                condition=models.Q(default=True),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_default(cls) -> Priority:
        return Priority.objects.get(default=True)

    @property
    def full_name(self) -> str:
        return f"{self.emoji} {self.name} - {self.description}"
