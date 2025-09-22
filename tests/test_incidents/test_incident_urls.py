from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse

from firefighter.incidents.factories import IncidentFactory, UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@pytest.mark.django_db
def test_incidents_dashboard_unauthorized(client: Client) -> None:
    """This test ensures that the incidents dashboard is not accessible, and that we are redirect to auth."""
    response = client.get(reverse("incidents:dashboard"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_incidents_list_unauthorized(client: Client) -> None:
    """This test ensures that the incidents page list is accessible."""
    response = client.get(reverse("incidents:incident-list"))

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incidents_statistics_unauthorized(client: Client) -> None:
    """This test ensures that the incidents statistics page is accessible."""
    response = client.get(reverse("incidents:incident-statistics"))

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incidents_dashboard_authorized(admin_client: Client, admin_user: User) -> None:
    """This test ensures that the incidents dashboard is accessible for an admin."""
    admin_client.force_login(admin_user)
    response = admin_client.get(reverse("incidents:dashboard"))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incidents_details(client: Client, admin_user: User) -> None:
    """This test ensures that the incidents dashboard is accessible for an admin."""
    user = UserFactory.create()
    incident = IncidentFactory.create(created_by=user)
    client.force_login(admin_user)
    response = client.get(
        reverse("incidents:incident-detail", kwargs={"incident_id": incident.id})
    )

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incidents_details_unauthorized_404_redirect(client: Client) -> None:
    """This test ensures that the incidents dashboard will return a 404."""
    response = client.get(
        reverse("incidents:incident-detail", kwargs={"incident_id": 119999})
    )

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incidents_details_authorized_404(client: Client, admin_user: User) -> None:
    """This test ensures that the incidents dashboard will return a 404."""
    client.force_login(admin_user)
    response = client.get(
        reverse("incidents:incident-detail", kwargs={"incident_id": 119999})
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incident_create_unauthorized(client: Client) -> None:
    """This test ensures that the incident create page is accessible."""
    response = client.get(reverse("incidents:incident-create"))

    # We expect a redirect to the login page
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incident_category_list(client: Client) -> None:
    """This test ensures that the incident category list is accessible."""
    response = client.get(reverse("incidents:incident-category-list"))

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.usefixtures("_debug")
def test_incident_list(client: Client) -> None:
    """This test ensures that the incident list is accessible."""
    response = client.get(reverse("incidents:incident-list"))

    assert response.status_code == 302
