from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from django.utils import timezone
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from firefighter.incidents.models import IncidentCategory
from firefighter.incidents.models.incident_category import IncidentCategoryFilterSet
from firefighter.incidents.tables import IncidentCategoriesTable

if TYPE_CHECKING:
    from django_tables2.tables import Table

    from firefighter.firefighter.utils import HtmxHttpRequest

logger = logging.getLogger(__name__)

TZ = timezone.get_current_timezone()


class IncidentCategoriesViewList(SingleTableMixin, FilterView):
    table_class = IncidentCategoriesTable
    context_object_name = "incident_categories"
    filterset_class = IncidentCategoryFilterSet
    model = IncidentCategory

    paginate_by = 150
    paginate_orphans = 20

    # XXX Export MTBF in API! Change defaults fields for component
    # XXX Help/documentation on the MTBF calculation
    # XXX MTBF when incidents are far appart ? Check and add a warning

    def get_table(self, **kwargs: Any) -> Table:
        table = super().get_table(**kwargs)
        # Hide MTBF and incident count if no date range is selected (they will be empty)
        if not self.request.GET or not self.request.GET.get("metrics_period"):
            table.exclude = ("mtbf", "incident_count")
        return table

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = "layouts/partials/partial_table_list_paginated.html"
        else:
            template_name = "pages/incident_category_list.html"

        return [template_name]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context["filter_order"] = [
            "search",
            "metrics_period",
            "group",
        ]
        context["page_title"] = "Issue categories list"
        return context
