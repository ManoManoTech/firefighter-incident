from __future__ import annotations

import contextlib
import enum
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from django.apps import apps
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from simple_menu import Menu, MenuItem

if TYPE_CHECKING:
    from django.http import HttpRequest

    from firefighter.firefighter.utils import AuthenticatedHttpRequest

APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME


class Menus(enum.StrEnum):
    main = "main"
    footer = "footer"


def user_details_url(request: AuthenticatedHttpRequest) -> str | None:
    """Return a personalized title for our profile menu item."""
    if request.user.is_authenticated:
        return request.user.get_absolute_url()
    return None  # type: ignore[unreachable]


def log_out_url(_request: HttpRequest) -> str:
    url = reverse("oidc_logout")
    return "?".join([
        url,
        urlencode({"next": "/admin/login/", "fail": "/admin/login/"}),
    ])


def setup_navbar_menu() -> None:
    submenu_items = [
        MenuItem(
            "Declare a critical incident",
            reverse("incidents:incident-create"),
            boost=False,
        ),
        MenuItem(
            "Statistics",
            reverse("incidents:incident-statistics"),
        ),
        MenuItem(
            "Incident categories",
            reverse("incidents:incident-category-list"),
        ),
    ]
    Menu.add_item(
        Menus.main,
        MenuItem(
            "Incidents",
            reverse(
                "incidents:incident-list",
            ),
            icon="menu-app",
            children=submenu_items,
        ),
    )

    if apps.is_installed("firefighter.pagerduty"):
        Menu.add_item(
            Menus.main,
            MenuItem(
                "On-calls",
                reverse("pagerduty:oncall-list"),
            ),
        )

    if apps.is_installed("firefighter.confluence"):
        knowledge_base_children = [
            MenuItem(
                "Runbooks",
                reverse("confluence:runbook_list"),
            ),
        ]
    else:
        knowledge_base_children = []
    Menu.add_item(
        Menus.main,
        MenuItem(
            "Knowledge Base",
            None,
            children=[
                *knowledge_base_children,
                MenuItem("Metrics Explanation", reverse("incidents:docs-metrics")),
                MenuItem("Role Types", reverse("incidents:docs-role-type-list")),
            ],
        ),
    )

    Menu.add_item(
        "user",
        MenuItem(
            "Profile",
            user_details_url,
            badge="Beta",
        ),
    )
    Menu.add_item(
        "user",
        MenuItem(
            "Back-office",
            reverse("admin:index"),
            check=lambda r: r.user.is_staff,
        ),
    )

    Menu.add_item(
        "user",
        MenuItem(
            "Log out",
            url=log_out_url,
            check=lambda r: r.user.is_authenticated,
        ),
    )


def setup_footer_menu() -> None:
    # XXX Link to FireFighter Github and documentation in default footer
    Menu.add_item(
        Menus.footer,
        MenuItem(
            APP_DISPLAY_NAME,
            None,
            children=[
                MenuItem("Github", "https://github.com/ManoManoTech/firefighter"),
            ],
        ),
    )

    with contextlib.suppress(NoReverseMatch):
        Menu.add_item(
            Menus.footer,
            MenuItem(
                f"{APP_DISPLAY_NAME} API",
                None,
                children=[
                    MenuItem("OpenAPI specs", reverse("api:schema")),
                    MenuItem("OpenAPI Swagger-UI", reverse("api:swagger-ui")),
                ],
            ),
        )


if not settings.FF_OVERRIDE_MENUS_CREATION:
    setup_navbar_menu()
    setup_footer_menu()
elif callable(settings.FF_OVERRIDE_MENUS_CREATION):
    settings.FF_OVERRIDE_MENUS_CREATION()
else:
    raise TypeError(
        "FF_OVERRIDE_MENUS_CREATION is not callable. "
        "Please provide a callable to override the menus creation."
    )
