from __future__ import annotations

import logging
from typing import Any

from django.db.models.query import Prefetch

from firefighter.firefighter.views import CustomDetailView
from firefighter.incidents.models import IncidentCategory

logger = logging.getLogger(__name__)


class IncidentCategoryDetailView(CustomDetailView[IncidentCategory]):
    template_name = "pages/incident_category_detail.html"
    context_object_name = "incident_category"
    pk_url_kwarg = "incident_category_id"
    model = IncidentCategory
    select_related = ["group"]

    queryset = IncidentCategory.objects.select_related(*select_related).prefetch_related(
        Prefetch("usergroups")
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        incident_category: IncidentCategory = context["incident_category"]

        additional_context = {
            "page_title": f"{incident_category.name} Incident Category",
        }

        return {**context, **additional_context}
