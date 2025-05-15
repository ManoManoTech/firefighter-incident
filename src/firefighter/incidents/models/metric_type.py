from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.models.milestone_type import (
    MilestoneType,
)


class MetricType(models.Model):
    name = models.CharField(
        max_length=50, help_text="Title or name (e.g. Time to Detect)"
    )
    code = models.CharField(
        max_length=10, unique=True, help_text="Short code (e.g. TTD)"
    )
    description = models.TextField()
    milestone_lhs = models.ForeignKey(
        MilestoneType,
        on_delete=models.CASCADE,
        related_name="metric_type_lhs",
        help_text="The milestone that ends the metric (duration = milestone_lhs - milestone_rhs)",
    )
    milestone_rhs = models.ForeignKey(
        MilestoneType,
        on_delete=models.CASCADE,
        related_name="metric_type_rhs",
        help_text="The milestone that starts the metric (duration = milestone_lhs - milestone_rhs)",
    )
    type = models.SlugField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Technical name, slugified version of the title (e.g. time_to_detect)",
    )

    class Meta(TypedModelMeta):
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__milestone_lhs_not_equal_milestone_rhs",
                check=~models.Q(milestone_lhs=models.F("milestone_rhs")),
                violation_error_message="The milestone that ends the metric cannot be the same as the milestone that starts the metric.",
            ),
        ]

        verbose_name = _("Metric Type")
        verbose_name_plural = _("Metric Types")

    def __str__(self) -> str:
        return self.name


class IncidentMetric(models.Model):
    incident = models.ForeignKey(
        "incidents.Incident",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="metric_set",
    )
    metric_type = models.ForeignKey(MetricType, on_delete=models.CASCADE, db_index=True)
    duration = models.DurationField(
        blank=False, validators=[MinValueValidator(timedelta(seconds=0))]
    )

    if TYPE_CHECKING:
        incident_id: int

    class Meta(TypedModelMeta):
        verbose_name = _("Incident Metric")
        verbose_name_plural = _("Incident Metrics")
        constraints = [
            models.UniqueConstraint(
                name="%(app_label)s_%(class)s__incident_metric_type_unique",
                fields=["incident", "metric_type"],
            ),
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__duration_positive",
                check=models.Q(duration__gte=timedelta(seconds=0)),
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.incident_id} - {self.metric_type} - {self.duration}"
