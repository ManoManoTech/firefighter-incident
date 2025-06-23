from __future__ import annotations

import uuid
from functools import cached_property
from typing import TYPE_CHECKING, Any, Protocol

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

if TYPE_CHECKING:
    from django.db.models.fields.related import ManyToManyField

    from firefighter.incidents.models.incident import Incident  # noqa: F401


class ImpactType(models.Model):
    emoji = models.CharField(max_length=5, default="▶")
    name = models.CharField(max_length=64)
    help_text = models.CharField(max_length=128)
    value = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField(default=10)

    class Meta(TypedModelMeta):
        verbose_name_plural = "Impact Types"

    def __str__(self) -> str:
        return self.name


class LevelChoices(models.TextChoices):
    HIGHEST = "HT", _("Highest")
    HIGH = "HI", _("High")
    MEDIUM = "MD", _("Medium")
    LOW = "LO", _("Low")
    LOWEST = "LT", _("Lowest")
    NONE = "NO", _("N/A")

    @property
    def priority(self) -> int:
        """Send level choice priority ."""
        priority_mapping = {
            self.HIGHEST: 1,
            self.HIGH: 2,
            self.MEDIUM: 3,
            self.LOW: 4,
            self.LOWEST: 5,
            self.NONE: 6,
        }
        return priority_mapping.get(self, 6)  # type: ignore [call-overload]

    @property
    def emoji(self) -> str:
        """Send emoji un function of priority."""
        none_emoji = ""
        emoji_mapping = {
            self.HIGHEST: "⏫",
            self.HIGH: "🔼",
            self.MEDIUM: "➡️",
            self.LOW: "🔽",
            self.LOWEST: "⏬",
            self.NONE: none_emoji,
        }
        return emoji_mapping.get(self, none_emoji)  # type: ignore [call-overload]


class ImpactLevel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    impact_type = models.ForeignKey(
        ImpactType, related_name="levels", on_delete=models.CASCADE, db_index=True
    )
    emoji = models.CharField(max_length=5, default="▶")
    name = models.CharField(
        max_length=75,
        blank=True,
        null=True,
        default="",
        help_text="Description for the impact level for this impact type.",
    )
    value = models.CharField(choices=LevelChoices.choices, max_length=2, default="NO")
    order = models.PositiveSmallIntegerField(default=10)
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed multi-line description for this impact level.",
    )
    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(
                fields=["impact_type", "value"], name="unique_impact_level"
            ),
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_value_valid",
                check=models.Q(value__in=LevelChoices.values),
            ),
        ]

    def __str__(self) -> str:
        return self.name or self.value

    @cached_property
    def value_label(self) -> str:
        return LevelChoices(self.value).label


class Impact(models.Model):
    impact_type = models.ForeignKey(
        "ImpactType", on_delete=models.CASCADE
    )
    impact_level = models.ForeignKey(
        ImpactLevel, on_delete=models.PROTECT
    )

    details = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.impact_type}: {self.impact_level}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Ensure impact_type matches impact_level.impact_type.

        Check constraints can't span relationships, so we have to do this manually.
        """
        if self.impact_type != self.impact_level.impact_type:
            raise ValidationError("impact_type must match impact_level.impact_type")


@receiver(pre_save, sender=Impact)
def validate_impact(sender: Any, instance: Impact, **kwargs: Any) -> None:
    instance.clean()


class IncidentImpact(models.Model):
    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE
    )
    impact = models.ForeignKey("Impact", on_delete=models.CASCADE)

    class Meta(TypedModelMeta):
        verbose_name = "Incident impact"
        verbose_name_plural = "Incident impacts"

    def __str__(self) -> str:
        return f"{self.incident} - {self.impact}"


class HasImpactProtocol(Protocol):
    id: Any
    impacts: ManyToManyField[Impact, Any]
