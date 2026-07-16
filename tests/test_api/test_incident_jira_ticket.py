"""Tests for ``_create_jira_ticket_for_api_incident`` (api/views/incidents.py).

Incidents created through the API must get a linked Jira ticket like the ones
opened through the Slack form. The helper takes the Jira fields from the incident,
creates the ticket best-effort, and never raises if Jira is unavailable.

Everything is mocked (no DB): the helper's DB/Jira calls are patched at their
source modules, and the incident is a stand-in with the attributes the helper reads.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from firefighter.api.views.incidents import _create_jira_ticket_for_api_incident


def _incident() -> MagicMock:
    inc = MagicMock()
    inc.id = 123
    inc.title = "[STG] datasets-builder failure"
    inc.description = "boom"
    inc.priority.value = 3
    inc.incident_category.name = "Spinak"
    inc.environment.value = "STG"
    inc.custom_fields = {}
    return inc


@patch("firefighter.raid.models.JiraTicket")
@patch("firefighter.raid.client.client")
@patch("firefighter.raid.service.get_jira_user_from_user")
@patch("firefighter.raid.forms.prepare_jira_fields")
def test_creates_jira_ticket_from_incident(
    mock_prepare: MagicMock,
    mock_get_jira_user: MagicMock,
    mock_client: MagicMock,
    mock_jira_ticket: MagicMock,
) -> None:
    mock_jira_ticket.objects.filter.return_value.exists.return_value = False
    mock_get_jira_user.return_value = MagicMock(id="jira-user-1")
    mock_prepare.return_value = {"summary": "t"}
    mock_client.create_issue.return_value = {"key": "INC-1", "id": "10001"}

    incident = _incident()
    _create_jira_ticket_for_api_incident(incident)

    # A ticket is created and linked to the incident.
    mock_client.create_issue.assert_called_once()
    mock_jira_ticket.objects.create.assert_called_once()
    _, create_kwargs = mock_jira_ticket.objects.create.call_args
    assert create_kwargs["incident"] is incident
    assert create_kwargs["key"] == "INC-1"

    # Fields are reconstructed from the incident (no form data).
    _, prep_kwargs = mock_prepare.call_args
    assert prep_kwargs["priority"] == 3
    assert prep_kwargs["environments"] == ["STG"]
    assert prep_kwargs["platforms"] == []
    assert prep_kwargs["impacts_data"] == {}
    assert prep_kwargs["reporter"] == "jira-user-1"
    assert prep_kwargs["incident_category"] == "Spinak"


@patch("firefighter.raid.models.JiraTicket")
@patch("firefighter.raid.client.client")
@patch("firefighter.raid.service.get_jira_user_from_user")
@patch("firefighter.raid.forms.prepare_jira_fields")
def test_best_effort_swallows_jira_errors(
    mock_prepare: MagicMock,
    mock_get_jira_user: MagicMock,
    mock_client: MagicMock,
    mock_jira_ticket: MagicMock,
) -> None:
    mock_jira_ticket.objects.filter.return_value.exists.return_value = False
    mock_get_jira_user.return_value = MagicMock(id="jira-user-1")
    mock_prepare.return_value = {"summary": "t"}
    mock_client.create_issue.side_effect = Exception("Jira is down")

    # Must NOT raise (incident is already created; Jira is best-effort).
    _create_jira_ticket_for_api_incident(_incident())

    mock_jira_ticket.objects.create.assert_not_called()


@patch("firefighter.raid.models.JiraTicket")
@patch("firefighter.raid.client.client")
def test_skips_when_ticket_already_exists(
    mock_client: MagicMock,
    mock_jira_ticket: MagicMock,
) -> None:
    mock_jira_ticket.objects.filter.return_value.exists.return_value = True

    _create_jira_ticket_for_api_incident(_incident())

    mock_client.create_issue.assert_not_called()
    mock_jira_ticket.objects.create.assert_not_called()
