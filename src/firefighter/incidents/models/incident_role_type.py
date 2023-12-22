from __future__ import annotations

from functools import cached_property
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class IncidentRoleType(models.Model):
    name = models.CharField[str, str](max_length=255)
    slug = models.SlugField[str, str](max_length=255, unique=True)
    emoji = models.CharField(
        max_length=5, blank=True, help_text=_("The emoji to represent this role.")
    )
    required = models.BooleanField(
        default=False,
        help_text=_(
            "If the role is required, it will be automatically attributed to the incident creator."
        ),
    )
    order = models.PositiveSmallIntegerField(
        help_text=_("The display order of the role."), default=0
    )

    # Short descriptions
    summary = models.TextField()
    summary_first_person = models.TextField(
        help_text=_(
            "First person version of the summary, used for instance in Slack messages to assignees."
        ),
        blank=True,
        null=True,
    )
    description = models.TextField()

    # Advanced descriptions (for documentation)
    aka = models.TextField(blank=True)

    class Meta:
        # Slug can only be alphanumerical and underscore, no dashes, to ease JSON usage with Slack API
        constraints = [
            models.CheckConstraint(
                check=models.Q(slug__regex=r"^[a-z0-9\_]+$"),
                name="incidents_incidentroletype_slug_check",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.slug = slugify(self.slug or self.name).replace("-", "_")
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("incidents:docs-role-type-detail", kwargs={"pk": self.pk})

    @cached_property
    def url(self) -> str:
        return urljoin(settings.BASE_URL, self.get_absolute_url())
