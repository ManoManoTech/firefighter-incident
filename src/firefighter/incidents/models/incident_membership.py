from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.models.user import User

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident  # noqa: F401
    from firefighter.incidents.models.incident_role_type import (  # noqa: F401
        IncidentRoleType,
    )


class IncidentMembership(models.Model):
    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE, db_index=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)

    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "user"], name="unique_incident_membership"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.incident}"


class IncidentRole(models.Model):
    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE, related_name="roles_set", db_index=True
    )
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="roles_set", db_index=True
    )
    role_type = models.ForeignKey(
        "IncidentRoleType",
        on_delete=models.CASCADE,
        related_name="roles_set",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "user", "role_type"], name="unique_incident_role"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.incident} - {self.role_type}"
