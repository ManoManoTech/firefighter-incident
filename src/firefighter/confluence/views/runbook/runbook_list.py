from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from firefighter.confluence.models import Runbook, RunbookFilterSet
from firefighter.confluence.tables import RunbookTable

if TYPE_CHECKING:
    from firefighter.firefighter.utils import HtmxHttpRequest

logger = logging.getLogger(__name__)


class RunbooksViewList(SingleTableMixin, FilterView):
    model = Runbook
    queryset = Runbook.objects.all()
    context_object_name = "runbooks"

    filterset_class = RunbookFilterSet

    table_class = RunbookTable
    paginate_by = 150
    paginate_orphans = 20

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = "layouts/partials/partial_table_list_paginated.html"
        else:
            template_name = "pages/runbook_list.html"

        return [template_name]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        context = super().get_context_data(**kwargs)
        context["filter_order"] = [
            "search",
            "service_type",
        ]
        context["page_title"] = "Runbooks List"
        return context
