from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.raid.serializers import JiraWebhookUpdateSerializer
from firefighter.raid.signals.incident_updated import (
    IMPACT_TO_JIRA_STATUS_MAP,
    incident_updated_close_ticket_when_mitigated_or_postmortem,
)


@pytest.mark.django_db
def test_jira_webhook_status_maps_and_sets_event_type(mocker) -> None:
    """Jira → Impact: status change maps and sets event_type=jira_status_sync."""
    incident = Incident.objects.create(
        title="inc",
        description="desc",
        priority_id=None,  # priority not required for status set
        incident_category_id=None,
        environment_id=None,
        created_by_id=None,
    )
    incident.create_incident_update = MagicMock()

    webhook_payload = {
        "issue": {"id": "123", "key": "IMPACT-1"},
        "changelog": {
            "items": [
                {
                    "field": "status",
                    "fromString": "In Progress",
                    "toString": "Reporter validation",
                }
            ]
        },
        "user": {"displayName": "jira-user"},
        "webhookEvent": "jira:issue_updated",
    }

    mock_ticket = SimpleNamespace(incident=incident)
    fake_qs = SimpleNamespace(get=lambda **kwargs: mock_ticket)
    with patch(
        "firefighter.raid.serializers.JiraTicket.objects.select_related",
        return_value=fake_qs,
    ):
        serializer = JiraWebhookUpdateSerializer(data=webhook_payload)
        assert serializer.is_valid(), serializer.errors
        serializer.save()

    incident.create_incident_update.assert_called_once()
    kwargs = incident.create_incident_update.call_args.kwargs
    assert kwargs["status"] == IncidentStatus.MITIGATED
    assert kwargs["event_type"] == "jira_status_sync"


@pytest.mark.django_db
def test_signal_skips_when_event_from_jira(mocker) -> None:
    """Impact → Jira: skip close/transition when event_type=jira_status_sync."""
    incident = SimpleNamespace(jira_ticket=SimpleNamespace(id="123"))
    incident_update = SimpleNamespace(
        status=IncidentStatus.CLOSED, event_type="jira_status_sync"
    )
    mock_close = mocker.patch(
        "firefighter.raid.signals.incident_updated.client.close_issue"
    )
    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=["_status"],
    )
    mock_close.assert_not_called()


@pytest.mark.django_db
def test_signal_transitions_non_close_status(mocker) -> None:
    """Impact → Jira: transitions mapped statuses to Jira."""
    incident = SimpleNamespace(
        jira_ticket=SimpleNamespace(id="123"),
        needs_postmortem=False,
    )
    incident_update = SimpleNamespace(status=IncidentStatus.MITIGATING, event_type=None)
    mock_transition = mocker.patch(
        "firefighter.raid.signals.incident_updated.client.transition_issue_auto"
    )

    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=["_status"],
    )

    target = IMPACT_TO_JIRA_STATUS_MAP[IncidentStatus.MITIGATING]
    mock_transition.assert_called_once_with("123", target, mocker.ANY)


@pytest.mark.django_db
def test_signal_transitions_mitigated_closes_for_p3_plus(mocker) -> None:
    """Impact → Jira: MITIGATED transitions to Reporter validation for P3+ (no postmortem)."""
    incident = SimpleNamespace(
        jira_ticket=SimpleNamespace(id="123"),
        needs_postmortem=False,
    )
    incident_update = SimpleNamespace(status=IncidentStatus.MITIGATED, event_type=None)
    mock_transition = mocker.patch(
        "firefighter.raid.signals.incident_updated.client.transition_issue_auto"
    )

    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=["_status"],
    )

    mock_transition.assert_called_once_with(
        "123", IMPACT_TO_JIRA_STATUS_MAP[IncidentStatus.MITIGATED], mocker.ANY
    )


@pytest.mark.django_db
def test_signal_mitigated_needs_postmortem_does_not_close(mocker) -> None:
    """Impact → Jira: MITIGATED does not close Jira when postmortem is needed."""
    incident = SimpleNamespace(
        jira_ticket=SimpleNamespace(id="123"),
        needs_postmortem=True,
    )
    incident_update = SimpleNamespace(status=IncidentStatus.MITIGATED, event_type=None)
    mock_transition = mocker.patch(
        "firefighter.raid.signals.incident_updated.client.transition_issue_auto"
    )

    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=["_status"],
    )

    mock_transition.assert_called_once_with(
        "123", IMPACT_TO_JIRA_STATUS_MAP[IncidentStatus.MITIGATED], mocker.ANY
    )


@pytest.mark.django_db
def test_signal_mitigating_runs_two_transitions(mocker) -> None:
    """Impact → Jira: MITIGATING triggers Pending resolution then in progress."""
    incident = SimpleNamespace(
        jira_ticket=SimpleNamespace(id="123"),
        needs_postmortem=False,
    )
    incident_update = SimpleNamespace(status=IncidentStatus.MITIGATING, event_type=None)
    mock_transition = mocker.patch(
        "firefighter.raid.signals.incident_updated.client.transition_issue_auto"
    )

    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=["_status"],
    )

    mock_transition.assert_has_calls(
        [
            mocker.call("123", "Pending resolution", mocker.ANY),
            mocker.call("123", "in progress", mocker.ANY),
        ]
    )
