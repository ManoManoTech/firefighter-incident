from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident_category import IncidentCategory
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.models.severity import Severity
from firefighter.incidents.models.user import User

if TYPE_CHECKING:
    import datetime

    from firefighter.incidents.models.incident import Incident  # noqa: F401

logger = logging.getLogger(__name__)


class IncidentUpdateManager(models.Manager["IncidentUpdate"]):
    def get_or_none(self, **kwargs: Any) -> IncidentUpdate | None:
        try:
            return self.get(**kwargs)
        except IncidentUpdate.DoesNotExist:
            return None


class IncidentUpdate(models.Model):
    """IncidentUpdate represents a single update to an incident.
    One incident can have many incident updates.
    Only updated fields are stored in the incident update.
    """

    objects: IncidentUpdateManager = IncidentUpdateManager()
    # TODO Separate all the statuses (now milestones)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.TextField(blank=True, null=True)
    _status = models.IntegerField(
        db_column="status",
        choices=IncidentStatus.choices,
        null=True,
        blank=True,
        verbose_name="Status",
    )
    severity = models.ForeignKey(
        Severity,
        null=True,
        blank=True,
        on_delete=models.SET(Severity.get_default),
        help_text="Superseded by priority",
    )
    severity.system_check_deprecated_details = {
        "msg": "The IncidentUpdate.severity field has been deprecated.",
        "hint": "Use IncidentUpdate.priority instead.",
        "id": "fields.W920",
    }
    priority = models.ForeignKey(
        Priority, null=True, blank=True, on_delete=models.SET(Priority.get_default)
    )
    environment = models.ForeignKey(
        Environment,
        null=True,
        blank=True,
        on_delete=models.SET(Environment.get_default),
    )
    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE
    )
    incident_category = models.ForeignKey(
        IncidentCategory, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    commander = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commander_for",
    )
    communication_lead = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="communication_lead_for",
    )

    title = models.CharField(null=True, blank=True, max_length=128)
    description = models.TextField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    event_ts: datetime.datetime = models.DateTimeField(
        auto_now_add=False, editable=True
    )  # type: ignore
    event_type = models.CharField(null=True, blank=True, max_length=64)

    class Meta(TypedModelMeta):
        ordering = ["-event_ts"]

        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__status_valid",
                check=models.Q(_status__in=IncidentStatus.values),
            )
        ]

    def __str__(self) -> str:
        if self.status:
            return f"{self.status.label}: {self.event_ts}"
        return f"{self.event_ts}"

    @property
    def status(self) -> IncidentStatus | None:
        if self._status:
            return IncidentStatus(self._status)
        return None

    @status.setter
    def status(self, status: IncidentStatus) -> None:
        self._status = status


@receiver(pre_save, sender=IncidentUpdate)
# pylint: disable=unused-argument
def set_event_ts(sender: Any, instance: IncidentUpdate, **kwargs: Any) -> None:
    """Add a timestamp on every IncidentUpdate.
    Not implemented using Django ORM auto_add as it would not make them user editable.
    """
    if instance.event_ts is None:
        instance.event_ts = timezone.now()  # type: ignore
