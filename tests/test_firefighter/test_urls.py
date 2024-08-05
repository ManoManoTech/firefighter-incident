from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest
from django.contrib.admin.sites import site
from django.http import HttpResponseRedirect
from django.urls import reverse

if TYPE_CHECKING:
    from django.test import Client

    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@pytest.mark.django_db
def test_health_check(client: Client) -> None:
    """This test ensures that health check is accessible."""
    response = client.get("/api/v2/firefighter/monitoring/healthcheck")

    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_unauthorized(client: Client) -> None:
    """This test ensures that admin panel requires auth."""
    response = client.get("/admin/")

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_admin_authorized(admin_client: Client, admin_user: User) -> None:
    """This test ensures that admin panel is accessible."""
    admin_client.force_login(admin_user)

    response = admin_client.get("/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_docs_unauthorized(client: Client) -> None:
    """This test ensures that admin panel docs requires auth."""
    response = client.get("/admin/doc/")

    assert isinstance(response, HttpResponseRedirect)
    assert response.status_code == 302
    assert response.url == "/admin/login/?next=/admin/doc/"


@pytest.mark.django_db
def test_admin_docs_authorized(admin_client: Client) -> None:
    """This test ensures that admin panel docs are accessible."""
    response = admin_client.get("/admin/doc/")

    assert response.status_code == 200
    assert b"docutils" not in response.content


@pytest.mark.django_db
def test_robotstxt_present(client: Client) -> None:
    """This test ensures that robots.txt is present."""
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert b"Disallow: /" in response.content


@pytest.mark.django_db
def test_login_sso_button_admin_login(client: Client) -> None:
    """This test ensures that login page contains the SSO button."""
    response = client.get("/admin/login/")

    assert response.status_code == 200
    assert b"Log in with SSO" in response.content


@pytest.mark.django_db
def test_error_500_pretty(client: Client) -> None:
    """This test ensures that 500 error page is pretty."""
    with pytest.raises(Exception, match="Test exception for 500"):  # noqa: PT012
        response = client.get("/err/500/")

        assert response.status_code == 500
        assert b"Please try again later, and report it" in response.content


@pytest.mark.django_db
def test_error_404_pretty(client: Client) -> None:
    """This test ensures that 404 error page is pretty."""
    response = client.get("/err/404/")

    assert response.status_code == 404
    assert b"Please check the URL in the address bar and try again" in response.content


@pytest.mark.django_db
def test_error_403_pretty(client: Client) -> None:
    """This test ensures that 403 error page is pretty."""
    response = client.get("/err/403/")

    assert response.status_code == 403
    assert b"You do not have permission to access this page." in response.content


@pytest.mark.django_db
def test_error_400_pretty(client: Client) -> None:
    """This test ensures that 400 error page is pretty."""
    response = client.get("/err/400/")

    assert response.status_code == 400
    assert b"Bad request" in response.content


def test_errors_json(client: Client) -> None:
    """This test ensures that error pages are in JSON when Accept header is set."""
    client.raise_request_exception = False
    for error_code in [400, 403, 404, 500]:
        response = client.get(f"/err/{error_code}/", {}, HTTP_ACCEPT="application/json")

        assert response.status_code == error_code
        assert response.headers["Content-Type"] == "application/json"
        assert json.loads(response.content).get("error") is not None


@pytest.mark.django_db
@pytest.mark.timeout(30)
@pytest.mark.usefixtures("_debug")
def test_all_admin_list_no_error(admin_client: Client, admin_user: User) -> None:
    """This test ensures that admin panel is accessible."""
    admin_client.force_login(admin_user)

    # Get all list admin urls for models that have an admin
    urls = [
        reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
        for model, model_admin in site._registry.items()
        if model_admin
    ]

    # Iterate over the list of urls and use the client to make get requests
    for url in urls:
        response = admin_client.get(url)
        # Check the status code of the response
        assert response.status_code == 200, f"Failed url is: {url}"
