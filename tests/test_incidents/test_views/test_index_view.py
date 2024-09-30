from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from firefighter.incidents.models.user import User


@pytest.mark.django_db
def test_main_page(client: Client, footer_text: str, admin_user: User) -> None:
    """This test ensures that main page works."""
    client.force_login(admin_user)
    response = client.get("/")

    assert response.status_code == 200
    assert footer_text in str(response.content)


@pytest.mark.django_db
def test_hello_page(client: Client, footer_text: str, admin_user: User) -> None:
    """This test ensures that dashboard page works."""
    client.force_login(admin_user)
    response = client.get(reverse("incidents:dashboard"))

    assert response.status_code == 200
    assert footer_text in str(response.content)
