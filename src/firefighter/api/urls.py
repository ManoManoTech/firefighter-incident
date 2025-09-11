from __future__ import annotations

from django.conf import settings
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import routers

from firefighter.api import views

app_name = "api"

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.include_root_view = False

router.register(
    r"environments",
    views.environments.EnvironmentViewSet,
    basename="environments",
)
router.register(
    r"incident_cost_types",
    views.incident_cost_types.IncidentCostTypeViewSet,
    basename="incident_cost_types",
)
router.register(
    r"incident_costs",
    views.incident_costs.IncidentCostViewSet,
    basename="incident_costs",
)
router.register(
    r"severities",
    views.severities.PriorityViewSet,
    basename="priorities",
)
# Legacy endpoint for backward compatibility
router.register(
    r"components",
    views.components.IncidentCategoryViewSet,
    basename="components",
)
# New preferred endpoint
router.register(
    r"incident-categories",
    views.components.IncidentCategoryViewSet,
    basename="incident-categories",
)
router.register(
    r"groups",
    views.groups.GroupViewSet,
    basename="groups",
)
router.register(
    r"incidents",
    views.incidents.IncidentViewSet,
    basename="incidents",
)


urlpatterns: list[URLPattern | URLResolver] = [
    path("", include(router.urls)),
    path(
        "incidents",
        views.incidents.CreateIncidentViewSet.as_view({"post": "create"}),  # pyright: ignore[reportGeneralTypeIssues]
        name="incidents",
    ),
]
if settings.FF_EXPOSE_API_DOCS:
    urlpatterns.extend((
        path(
            "schema",
            SpectacularAPIView.as_view(),  # pyright: ignore[reportGeneralTypeIssues]
            name="schema",
        ),
        path(
            "schema/swagger-ui",
            SpectacularSwaggerView.as_view(url_name="api:schema"),  # pyright: ignore[reportGeneralTypeIssues]
            name="swagger-ui",
        ),
    ))
