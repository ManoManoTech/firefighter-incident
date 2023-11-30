from __future__ import annotations

import logging
from typing import Any

from django.db.models.query import Prefetch

from firefighter.firefighter.views import CustomDetailView
from firefighter.incidents.models import Component

logger = logging.getLogger(__name__)


class ComponentDetailView(CustomDetailView[Component]):
    template_name = "pages/component_detail.html"
    context_object_name = "component"
    pk_url_kwarg = "component_id"
    model = Component
    select_related = ["group"]

    queryset = Component.objects.select_related(*select_related).prefetch_related(
        Prefetch("usergroups")
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        component: Component = context["component"]

        additional_context = {
            "page_title": f"{component.name} Component",
        }

        return {**context, **additional_context}
