from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q
from django.views.generic.base import TemplateView

from firefighter.incidents.models.metric_type import MetricType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from firefighter.incidents.models.milestone_type import MilestoneType


class MetricsView(TemplateView):
    template_name = "pages/docs_metrics.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        metric_types = MetricType.objects.filter(
            Q(milestone_lhs__asked_for=True) & Q(milestone_rhs__asked_for=True)
        ).select_related("milestone_lhs", "milestone_rhs")
        milestone_types = {metric.milestone_lhs for metric in metric_types} | {
            metric.milestone_rhs for metric in metric_types
        }
        context["key_events"] = milestone_types
        context["metrics"] = metric_types
        context["metric_graph"] = self.generate_metrics_mermaid_graph(
            milestone_types, metric_types
        )
        context["page_title"] = "Metrics Explanation"
        return context

    @staticmethod
    def generate_metrics_mermaid_graph(
        milestone_types: Iterable[MilestoneType],
        metric_types: Iterable[MetricType],
    ) -> list[str]:
        participants = [
            f"participant {milestone.name.title()}" for milestone in milestone_types
        ]
        messages = [
            f"{metric.milestone_lhs.name}->{metric.milestone_rhs.name}: {metric.name} ({metric.code})"
            for metric in metric_types
        ]
        return ["sequenceDiagram", *participants, *messages]
