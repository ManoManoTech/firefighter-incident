from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from firefighter.firefighter.views import CustomDetailView
from firefighter.incidents.models import IncidentRoleType

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseRedirect


class RoleTypeListView(ListView[IncidentRoleType]):
    model = IncidentRoleType
    template_name = "pages/incident_role_types_list.html"
    context_object_name = "incident_role_types_list"
    ordering = ["order", "name"]


class RoleTypeDetailView(CustomDetailView[IncidentRoleType]):
    model = IncidentRoleType
    template_name = "pages/incident_role_types_detail.html"
    context_object_name = "incident_role_type"


class RoleTypeRedirectView(View):
    @staticmethod
    def get(
        request: HttpRequest,  # noqa: ARG004
        slug: str | None = None,
    ) -> HttpResponseRedirect:
        incident_role_type = get_object_or_404(IncidentRoleType, slug=slug)
        return redirect(incident_role_type)
