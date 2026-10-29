from __future__ import annotations

import uuid

from django.db import models
from django.db.models.functions import Lower
from django.db.models.manager import Manager
from django.utils.text import slugify

from firefighter.incidents.models.user import User


class PartnerManager(Manager["Partner"]):
    def get_or_create_by_name(
        self, name: str, *, created_by: User | None = None
    ) -> tuple[Partner, bool]:
        """Return the partner with this name (case and spacing insensitive), creating it if needed.

        A partner added by a user is created as not reviewed, so that someone curates
        the list (rename, merge a duplicate, deactivate) from the admin.
        """
        clean_name = " ".join(name.split())
        if not clean_name:
            err_msg = "A partner name cannot be empty"
            raise ValueError(err_msg)
        slug = slugify(clean_name)
        existing = self.filter(name__iexact=clean_name).first() or (
            self.filter(slug=slug).first() if slug else None
        )
        if existing is not None:
            return existing, False
        partner = self.create(
            name=clean_name,
            slug=slug or uuid.uuid4().hex[:12],
            is_reviewed=False,
            created_by=created_by,
        )
        return partner, True


class Partner(models.Model):
    """A third-party provider the platform depends on (search, CDN, payment...).

    The list is curated in the admin, but a Commander can add a missing partner
    when recording the origin of an incident.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive partners are no longer offered, but stay on past incidents.",
    )
    is_reviewed = models.BooleanField(
        default=True,
        help_text="False for a partner added by a user, until someone checks it is not a duplicate.",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PartnerManager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="%(app_label)s_%(class)s_unique_name_ci"
            ),
        ]

    def __str__(self) -> str:
        return self.name
