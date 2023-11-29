from __future__ import annotations

from django.urls import path

from incidents.views import views
from incidents.views.components.details import ComponentDetailView
from incidents.views.components.list import ComponentsViewList
from incidents.views.docs.metrics import MetricsView
from incidents.views.docs.role_types import (
    RoleTypeDetailView,
    RoleTypeListView,
    RoleTypeRedirectView,
)
from incidents.views.users.details import UserDetailView

app_name = "incidents"

urlpatterns = [
    # Incidents app views
    path("", views.DashboardView.as_view(), name="dashboard"),
    path(
        "incident/create/", views.IncidentCreateView.as_view(), name="incident-create"
    ),
    path("incident/", views.IncidentListView.as_view(), name="incident-list"),
    path(
        "incident/<int:incident_id>/",
        views.IncidentDetailView.as_view(),
        name="incident-detail",
    ),
    path(
        "incident/<int:incident_id>/update_key_events/",
        views.IncidentUpdateKeyEventsView.as_view(),
        name="incident-update-key-events",
    ),
    path(
        "statistics/",
        views.IncidentStatisticsView.as_view(),
        name="incident-statistics",
    ),
    path("component/", ComponentsViewList.as_view(), name="component-list"),
    path(
        "component/<uuid:component_id>/",
        ComponentDetailView.as_view(),
        name="component-detail",
    ),
    path(
        "user/<uuid:user_id>/",
        UserDetailView.as_view(),
        name="user-detail",
    ),
    path(
        "docs/metrics/",
        MetricsView.as_view(),
        name="docs-metrics",
    ),
    path("docs/role_types/", RoleTypeListView.as_view(), name="docs-role-type-list"),
    path(
        "docs/role_types/<int:pk>/",
        RoleTypeDetailView.as_view(),
        name="docs-role-type-detail",
    ),
    path(
        "docs/role_types/<slug:slug>/",
        RoleTypeRedirectView.as_view(),
        name="docs-role-type-detail-slug-redirect",
    ),
]
