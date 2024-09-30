from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.factories import UserFactory

if TYPE_CHECKING:
    from django.test import Client

    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


def test_api_schema(client: Client) -> None:
    """This test ensures that the schema is accessible."""
    response = client.get("/api/v2/firefighter/schema")

    assert response.status_code == 200


@pytest.mark.django_db
def test_incidents_cost_api(admin_client: Client, admin_user: User) -> None:
    """This test ensures that the incidents costs API endpoint is accessible for an admin"""
    admin_client.force_login(admin_user)
    response = admin_client.get("/api/v2/firefighter/incident_costs/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_incidents_cost_api_unauthorized(client: Client) -> None:
    """This test ensures that the incidents costs API endpoint is not accessible for a guest user"""
    user = UserFactory.create()
    client.force_login(user)
    response = client.get("/api/v2/firefighter/incident_costs/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_incidents_cost_type_api(admin_client: Client, admin_user: User) -> None:
    """This test ensures that the incidents cost types API endpoint is accessible for an admin"""
    admin_client.force_login(admin_user)
    response = admin_client.get("/api/v2/firefighter/incident_cost_types/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_incidents_cost_api_type_unauthorized(client: Client) -> None:
    """This test ensures that the incidents costs API endpoint is not accessible for a guest user"""
    user = UserFactory.create()
    client.force_login(user)
    response = client.get("/api/v2/firefighter/incident_costs/")

    assert response.status_code == 403
