from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident  # noqa: F401
    from firefighter.incidents.models.incident_cost_type import (  # noqa: F401
        IncidentCostType,
    )


class IncidentCost(models.Model):
    """Incident Cost is inspired from dispatch."""

    id = models.BigAutoField(primary_key=True)

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount in EUR",
    )
    details = models.TextField(null=True, blank=True)

    cost_type = models.ForeignKey(
        "IncidentCostType", on_delete=models.CASCADE, related_name="incident_cost_set"
    )
    incident = models.ForeignKey(
        "Incident", on_delete=models.CASCADE, related_name="incident_cost_set"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        verbose_name = "Incident cost"
        verbose_name_plural = "Incident costs"

    def __str__(self) -> str:
        return f"{self.cost_type.name} - {self.amount}"

    @property
    def currency(self) -> str:
        return "EUR"
