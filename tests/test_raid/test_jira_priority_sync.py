from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.group import Group
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_category import IncidentCategory
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.models.user import User
from firefighter.raid.serializers import JiraWebhookUpdateSerializer


@pytest.fixture(autouse=True)
def clear_sync_cache() -> None:
    cache.clear()


@pytest.fixture(autouse=True)
def patch_alert_slack_update_ticket(mocker: pytest.MockFixture) -> MagicMock:
    return mocker.patch(
        "firefighter.raid.serializers.alert_slack_update_ticket", return_value=True
    )


def _make_incident() -> Incident:
    creator = User.objects.create(
        email="creator@example.com",
        username="creator",
        first_name="c",
        last_name="u",
    )
    category = IncidentCategory.objects.first()
    if category is None:
        group = Group.objects.first() or Group.objects.create(
            name="Default Group", description="grp", order=0
        )
        category = IncidentCategory.objects.create(
            name="Default Category", description="", order=0, group=group
        )
    incident = Incident.objects.create(
        title="inc",
        description="desc",
        priority=Priority.get_default(),
        incident_category=category,
        environment=Environment.get_default(),
        created_by=creator,
    )
    incident.create_incident_update = MagicMock()
    return incident


def _run_webhook(incident: Incident, change_item: dict) -> None:
    payload = {
        "issue": {"id": "123", "key": "IMPACT-1"},
        "changelog": {"items": [change_item]},
        "user": {"displayName": "jira-user"},
        "webhookEvent": "jira:issue_updated",
    }
    mock_ticket = SimpleNamespace(incident=incident)
    fake_qs = SimpleNamespace(get=lambda **kwargs: mock_ticket)
    with patch(
        "firefighter.raid.serializers.JiraTicket.objects.select_related",
        return_value=fake_qs,
    ):
        serializer = JiraWebhookUpdateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        serializer.save()


@pytest.mark.django_db
def test_story_points_change_does_not_flip_priority() -> None:
    """Regression: a Story Points change (customfield_10008) whose value is 1-5 must
    NOT be misread as a priority change. This is the AFP-4216 bug (Story Points=2
    flipped the incident to P2)."""
    incident = _make_incident()

    _run_webhook(
        incident,
        {
            "field": "Story Points",
            "fieldId": "customfield_10008",
            "fromString": None,
            "toString": "2",
        },
    )

    incident.create_incident_update.assert_not_called()


@pytest.mark.django_db
def test_customfield_11064_change_syncs_priority() -> None:
    """Jira → Impact: a real change of the FF priority field (customfield_11064)
    must sync the incident priority with event_type=jira_priority_sync."""
    Priority.objects.get_or_create(
        value=2,
        defaults={
            "name": "P2",
            "order": 2,
            "description": "",
            "needs_postmortem": True,
        },
    )
    incident = _make_incident()

    _run_webhook(
        incident,
        {
            "field": "Priority",
            "fieldId": "customfield_11064",
            "fromString": "4",
            "toString": "2",
        },
    )

    incident.create_incident_update.assert_called_once()
    kwargs = incident.create_incident_update.call_args.kwargs
    assert kwargs["event_type"] == "jira_priority_sync"


@pytest.mark.django_db
def test_standard_priority_field_does_not_sync() -> None:
    """Impact owns customfield_11064, not the standard Jira priority field. A change
    of the standard `priority` field must NOT flip the incident (kills the historical
    Resolution=Done -> Highest propagation vector)."""
    incident = _make_incident()

    _run_webhook(
        incident,
        {
            "field": "priority",
            "fieldId": "priority",
            "fromString": "Medium",
            "toString": "Highest",
        },
    )

    incident.create_incident_update.assert_not_called()
