from __future__ import annotations

import logging
from typing import Any

from django.views import generic

from firefighter.pagerduty.models import PagerDutyEscalationPolicy, PagerDutyOncall

logger = logging.getLogger(__name__)


class OncallListView(generic.ListView[PagerDutyOncall]):
    template_name = "pages/oncall_list.html"
    context_object_name = "oncalls"

    @staticmethod
    def get_queryset() -> list[tuple[PagerDutyEscalationPolicy, list[PagerDutyOncall]]]:  # type: ignore[override]
        return PagerDutyOncall.objects.get_current_oncalls_per_escalation_policy()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        last_fetched = (
            PagerDutyOncall.objects.values("updated_at").order_by("-updated_at").first()
        )
        context["last_updated"] = last_fetched["updated_at"] if last_fetched else None
        context["page_title"] = "On-call Overview"
        return context
