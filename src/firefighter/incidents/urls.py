from __future__ import annotations

from django.urls import path

from firefighter.incidents.views import views
from firefighter.incidents.views.components.details import IncidentCategoryDetailView
from firefighter.incidents.views.components.list import IncidentCategoriesViewList
from firefighter.incidents.views.docs.metrics import MetricsView
from firefighter.incidents.views.docs.role_types import (
    RoleTypeDetailView,
    RoleTypeListView,
    RoleTypeRedirectView,
)
from firefighter.incidents.views.users.details import UserDetailView

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
    path("incident-category/", IncidentCategoriesViewList.as_view(), name="incident-category-list"),
    path(
        "incident-category/<uuid:incident_category_id>/",
        IncidentCategoryDetailView.as_view(),
        name="incident-category-detail",
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
