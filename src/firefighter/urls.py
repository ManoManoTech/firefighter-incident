"""firefighter URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/

## Examples:

### Function views

1. Add an import:  `from my_app import views`
2. Add a URL to urlpatterns:  `path('', views.home, name='home')`

### Class-based views

1. Add an import:  `from other_app.views import Home`
2. Add a URL to urlpatterns:  `path('', Home.as_view(), name='home')`

### Including another URLconf

1. Import the include() function: `from django.urls import include, path`
2. Add a URL to urlpatterns:  `path('blog/', include('blog.urls'))`
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from django.apps import apps
from django.conf import settings
from django.urls import URLPattern, URLResolver, include, path
from django.views.generic.base import TemplateView

from firefighter import views
from firefighter.admin import admin_custom

if TYPE_CHECKING:
    from collections.abc import Sequence

handler404 = "incidents.views.errors.page_not_found"
handler403 = "incidents.views.errors.permission_denied"
handler400 = "incidents.views.errors.bad_request"
handler500 = "incidents.views.errors.server_error"

app_name = "firefighter"
firefighter_urlpatterns: tuple[Sequence[URLResolver | URLPattern], str] = (
    [
        path("err/403/", views.permission_denied_view),
        path("err/404/", views.not_found_view),
        path("err/400/", views.bad_request_view),
        path("err/500/", views.server_error_view),
        path(
            "robots.txt",
            TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        ),
        path(
            "api/v2/firefighter/monitoring/healthcheck",
            views.healthcheck,
            name="healthcheck",
        ),
    ],
    "firefighter",
)

urlpatterns = [
    # Both OIDC and admindocs are hardcoded with no namespace
    path("oidc/", include("oauth2_authcodeflow.urls")),
    path("admin/doc/", include("django.contrib.admindocs.urls")),
    path("admin/", admin_custom.site.urls),
    path("", include("incidents.urls")),
    path("api/v2/firefighter/", include("api.urls", namespace="api")),
    path("", include(firefighter_urlpatterns)),
    # Slack URLs are included later if needed (see slack/apps.py)
]
if apps.is_installed("pagerduty"):
    urlpatterns.insert(
        4,
        path("", include("pagerduty.urls")),
    )
if apps.is_installed("confluence"):
    urlpatterns.insert(
        5,
        path("", include("confluence.urls")),
    )

if settings.ENV == "dev":
    urlpatterns.append(
        path("__reload__/", include("django_browser_reload.urls")),
    )
    if settings.DEBUG_SILK:
        urlpatterns.append(path("silk/", include("silk.urls", namespace="silk")))
    if settings.DEBUG_TOOLBAR:
        import debug_toolbar

        urlpatterns.append(
            path("__debug__/", include(debug_toolbar.urls)),
        )

if apps.is_installed("slack") and (
    "runserver" in sys.argv
    or "firefighter.wsgi" in sys.argv
    or "main.py" in sys.argv
    or (len(sys.argv) > 0 and "ff-web" in sys.argv[0])
):
    # Only add the routes when running the server.
    # Else, a Slack client will be created for every command, making a Slack API call for authorization.
    # All commands would be impacted (migrate, ...)
    # XXX Add URLs for Slack tests

    urlpatterns.append(
        path("api/v2/firefighter/slack/", include("slack.urls")),
    )
