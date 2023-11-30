from __future__ import annotations

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta


class IncidentCostType(models.Model):
    """Incident Cost Type is inspired from dispatch."""

    id = models.BigAutoField(primary_key=True)

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)

    default = models.BooleanField(default=False)
    editable = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        verbose_name = "Incident cost type"
        verbose_name_plural = "Incident cost types"

    def __str__(self) -> str:
        return self.name
