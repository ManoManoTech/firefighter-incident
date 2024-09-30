from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from firefighter.incidents.models import Incident
from firefighter.incidents.models.user import User


@pytest.mark.django_db
def test_incident_detail_view(
    client: Client, footer_text: str, incident_saved: Incident, admin_user: User
) -> None:
    """This test ensures that incident detail page works."""
    client.force_login(admin_user)
    response = client.get(
        reverse("incidents:incident-detail", args=[incident_saved.id])
    )

    assert response.status_code == 200
    assert footer_text in str(response.content)

    incident_saved.delete()
