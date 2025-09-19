from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.query import Prefetch
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views import generic
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from firefighter.firefighter.views import CustomDetailView
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms import CreateIncidentForm
from firefighter.incidents.forms.update_key_events import IncidentUpdateKeyEventsForm
from firefighter.incidents.models.impact import Impact
from firefighter.incidents.models.incident import Incident, IncidentFilterSet
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.metric_type import IncidentMetric
from firefighter.incidents.signals import (
    create_incident_conversation,
    incident_key_events_updated,
)
from firefighter.incidents.tables import IncidentTable
from firefighter.incidents.views.reports import weekly_dashboard_context

if TYPE_CHECKING:
    from firefighter.firefighter.utils import HtmxHttpRequest

logger = logging.getLogger(__name__)


class IncidentListView(SingleTableMixin, FilterView):
    table_class = IncidentTable
    context_object_name = "incidents"
    filterset_class = IncidentFilterSet
    model = Incident

    paginate_by = 125
    paginate_orphans = 15
    queryset = Incident.objects.select_related(
        "priority", "incident_category__group", "environment"
    ).order_by("-id")

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = "layouts/partials/partial_table_list_paginated.html"
        else:
            template_name = "pages/incident_list.html"

        return [template_name]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context["page_range"] = context["table"].paginator.get_elided_page_range(
            context["table"].page.number, on_each_side=2, on_ends=1
        )
        context["filter_order"] = [
            "search",
            "created_at",
            "status",
            "environment",
            "priority",
            "incident_category",
        ]

        context["page_title"] = "Incidents List"
        context["api_url_export"] = reverse("api:incidents-list")
        return context


class IncidentStatisticsView(FilterView):
    context_object_name = "incidents_filtered"
    filterset_class = IncidentFilterSet
    model = Incident
    queryset = (
        Incident.objects.select_related("priority", "incident_category__group", "environment")
        .all()
        .order_by("-id")
    )

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = "pages/incident_statistics_partial.html"
        else:
            template_name = "pages/incident_statistics.html"
        return [template_name]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Statistics"
        context["filter_order"] = [
            "search",
            "created_at",
            "status",
            "environment",
            "priority",
            "incident_category",
        ]
        context_data = weekly_dashboard_context(
            self.request, context.get("incidents_filtered", [])
        )
        return {**context, **context_data}


class DashboardView(generic.ListView[Incident]):
    template_name = "pages/dashboard.html"
    context_object_name = "incidents"
    sub = (
        IncidentUpdate.objects.filter(incident_id=OuterRef("id"))
        .order_by("-event_ts")
        .values("event_ts")[:1]
    )
    queryset = (
        Incident.objects.filter(_status__lt=IncidentStatus.CLOSED)
        .select_related("priority", "incident_category__group", "environment", "created_by")
        .order_by("_status", "priority__value")
        .annotate(latest_event_ts=Subquery(sub.values("event_ts")))
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """No *args to pass."""
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Incidents Dashboard"
        return context


class IncidentDetailView(CustomDetailView[Incident]):
    template_name = "pages/incident_detail.html"
    context_object_name: str = "incident"
    pk_url_kwarg = "incident_id"
    model = Incident
    select_related = [
        "priority",
        "environment",
        "incident_category__group",
        "conversation",
        "created_by",
    ]
    if settings.ENABLE_CONFLUENCE:
        select_related.append("postmortem_for")
    queryset = Incident.objects.select_related(*select_related).prefetch_related(
        Prefetch(
            "incidentupdate_set",
            queryset=IncidentUpdate.objects.select_related(
                "priority",
                "incident_category__group",
                "created_by__slack_user",
                "created_by",
                "commander",
                "communication_lead",
            ).order_by("-event_ts"),
        ),
        Prefetch(
            "metrics", queryset=IncidentMetric.objects.select_related("metric_type")
        ),
        Prefetch(
            "impacts",
            queryset=Impact.objects.select_related("impact_type", "impact_level"),
        ),
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        incident: Incident = context["incident"]

        additional_context = {
            "page_title": f"Incident #{incident.id}",
        }

        return {**context, **additional_context}


class IncidentCreateView(LoginRequiredMixin, generic.edit.FormView[CreateIncidentForm]):
    login_url = "/oidc/authenticate?fail=/admin/login/"
    form_class = CreateIncidentForm
    template_name = "pages/incident_create.html"

    def form_valid(self, form: CreateIncidentForm) -> ProcessAfterResponse:
        incident = Incident.objects.declare(
            **form.cleaned_data,
            created_by=self.request.user,
        )
        # Redirect to the new incident page:
        return ProcessAfterResponse(
            reverse("incidents:incident-detail", args=(incident.id,)),
            data={
                "incident": incident,
                "user": self.request.user,
            },
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Declare Critical Incident"
        return context


class IncidentUpdateKeyEventsView(
    generic.detail.SingleObjectMixin[Incident],
    LoginRequiredMixin,
    generic.FormView[IncidentUpdateKeyEventsForm],
):
    form_class = IncidentUpdateKeyEventsForm
    context_object_name = "incident"
    pk_url_kwarg = "incident_id"
    success_url = reverse_lazy("incidents:incident-list")
    model = Incident
    object: Incident

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = (
                "layouts/partials/incident_update_key_events_view_modal.html"
            )

        else:
            template_name = "pages/incident_update_key_events_form.html"
        return [template_name]

    def get_form(
        self, form_class: type[IncidentUpdateKeyEventsForm] | None = None
    ) -> IncidentUpdateKeyEventsForm:
        """Replace Markdown bold syntax with HTML bold syntax in form labels."""
        form = super().get_form(form_class)
        for field in form.fields:
            # Replace *ABC* with <bold>ABC</bold>
            form.fields[field].label = re.sub(
                r"\*(.*?)\*", r"<b>\1</b>", str(form.fields[field].label)
            )
        return form

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: IncidentUpdateKeyEventsForm) -> HttpResponse:
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.

        form.save()
        # Send signal so we can update the Slack message if applicable
        logger.debug("Sending signal incident_key_events_updated")
        incident_key_events_updated.send_robust(
            __name__,
            incident=form.incident,
        )
        form.incident.compute_metrics()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("incidents:incident-detail", args=(self.object.id,))

    def get_form_kwargs(self) -> dict[str, Any]:
        return super().get_form_kwargs() | {
            "incident": self.object,
            "user": self.request.user,
        }


class ProcessAfterResponse(HttpResponseRedirect):
    """Custom Response, to trigger the Slack workflow after creating the incident and returning HTTP 201.

    TODO This does not work, the workflow is triggered before the response is sent. We need to do a celery task!
    TODO We need to redirect to the incident page or Slack conversation.
    """

    def __init__(
        self, redirect_to: str, data: dict[str, Any], *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(redirect_to, *args, **kwargs)
        self.data = data

    def close(self) -> None:
        super().close()
        incident = self.data["incident"]
        create_incident_conversation.send(
            "create-incident",
            incident=incident,
        )
