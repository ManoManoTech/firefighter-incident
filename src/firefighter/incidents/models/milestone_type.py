"""MilestoneType model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

if TYPE_CHECKING:
    import datetime


@dataclass
class MilestoneData:
    event_ts: datetime.datetime | None


def milestone_data_factory() -> MilestoneData:
    return MilestoneData(
        None,
    )


class MilestoneType(models.Model):
    """Represents a milestone type, also known as a key event time or event time."""

    name = models.CharField[str, str](
        max_length=50, help_text="Title or name (e.g. Recovered)"
    )
    event_type = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Technical name, slugified version of the name (e.g. recovered)",
    )

    summary = models.CharField(
        max_length=250,
        help_text="Slack Markdown summary of the milestone (e.g. *Recovered*, when the impact is no longer apparent.)",
    )
    user_editable = models.BooleanField[bool, bool](
        help_text="Can be edited by users (else, system event)."
    )
    required = models.BooleanField[bool, bool](
        help_text="Is required for the incident to be considered as complete."
    )
    asked_for = models.BooleanField[bool, bool](
        default=True, help_text="Asked for in the form."
    )
    description = models.TextField(blank=True, null=True)

    class Meta(TypedModelMeta):
        verbose_name = _("Milestone Type")
        verbose_name_plural = _("Milestone Types")

    def __str__(self) -> str:
        return self.summary


@dataclass
class MilestoneTypeData:
    milestone_type: MilestoneType
    data: MilestoneData = field(default_factory=milestone_data_factory)
