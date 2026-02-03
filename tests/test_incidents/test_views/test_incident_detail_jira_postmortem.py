"""Test incident detail view displays Jira post-mortem links."""

from __future__ import annotations

import pytest
from django.apps import apps
from django.test import Client
from django.urls import reverse

from firefighter.incidents.models import Incident
from firefighter.incidents.models.user import User

pytestmark = pytest.mark.skipif(
    not apps.is_installed("firefighter.jira_app"),
    reason="Jira app not installed",
)


@pytest.mark.django_db
def test_incident_detail_view_with_jira_postmortem(
    client: Client, incident_saved: Incident, admin_user: User
) -> None:
    """Test that Jira post-mortem link is displayed when it exists."""
    from firefighter.jira_app.models import JiraPostMortem

    # Create a Jira post-mortem for the incident
    JiraPostMortem.objects.create(
        incident=incident_saved,
        jira_issue_key="INCIDENT-123",
        jira_issue_id="10001",
        created_by=admin_user,
    )

    client.force_login(admin_user)
    response = client.get(
        reverse("incidents:incident-detail", args=[incident_saved.id])
    )

    assert response.status_code == 200
    response_content = str(response.content)

    # Check that the post-mortem section is present
    assert "Post-mortem" in response_content

    # Check that the Jira issue key is displayed
    assert "INCIDENT-123" in response_content

    # Check that the URL is correctly formed
    assert "browse/INCIDENT-123" in response_content


@pytest.mark.django_db
def test_incident_detail_view_without_jira_postmortem(
    client: Client, incident_saved: Incident, admin_user: User
) -> None:
    """Test that incident detail view works without Jira post-mortem."""
    client.force_login(admin_user)
    response = client.get(
        reverse("incidents:incident-detail", args=[incident_saved.id])
    )

    assert response.status_code == 200
    # Page should load successfully even without post-mortem
