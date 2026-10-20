"""Tests for the UnifiedIncidentForm paths not reached by the integration tests.

- Jira ticket creation for a P1-P3 incident that already has its Slack channel.
- The default priority initial value.
- The form still builds when the RAID app cannot be imported.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.forms.unified_incident import (
    UnifiedIncidentForm,
    initial_priority,
)
from firefighter.incidents.models import Priority
from firefighter.jira_app.models import JiraUser
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentDeclaredAnnouncement,
)
from firefighter.slack.models.incident_channel import IncidentChannel

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.django_db
def test_initial_priority_is_the_default_priority() -> None:
    Priority.objects.update(default=False)
    default = Priority.objects.order_by("value").first()
    assert default is not None
    default.default = True
    default.save()

    assert initial_priority() == default


@pytest.mark.django_db
def test_form_builds_without_the_raid_app(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A None entry in sys.modules makes `from firefighter.raid.models import ...` raise ImportError
    monkeypatch.setitem(sys.modules, "firefighter.raid.models", None)

    with caplog.at_level(logging.WARNING):
        form = UnifiedIncidentForm()

    assert "suggested_team_routing" in form.fields
    assert "RAID module not available" in caplog.text


@pytest.mark.django_db
class TestCreateJiraTicketForIncidentWithChannel:
    @staticmethod
    def test_links_the_ticket_and_the_channel(mocker: MockerFixture) -> None:
        creator = UserFactory.create()
        jira_user = JiraUser.objects.create(id="jira-creator", user=creator)
        p1 = Priority.objects.get_or_create(value=1, defaults={"name": "P1"})[0]
        incident = IncidentFactory.create(priority=p1, created_by=creator)
        channel = IncidentChannelFactory.create(incident=incident)
        incident.refresh_from_db()

        jira_client = mocker.patch("firefighter.raid.client.client")
        jira_client.create_issue.return_value = {"key": "INC-1"}
        mocker.patch(
            "firefighter.raid.service.get_jira_user_from_user", return_value=jira_user
        )
        prepare_jira_fields = mocker.patch(
            "firefighter.raid.forms.prepare_jira_fields", return_value={"summary": "x"}
        )
        mocker.patch("firefighter.raid.forms.set_jira_ticket_watchers_raid")
        jira_ticket = MagicMock(id=4242, url="https://jira.example/browse/INC-1")
        mocker.patch(
            "firefighter.raid.models.JiraTicket.objects.create", return_value=jira_ticket
        )
        mocker.patch("firefighter.incidents.forms.unified_incident.SelectImpactForm")
        add_bookmark = mocker.patch.object(IncidentChannel, "add_bookmark")
        send_message = mocker.patch.object(IncidentChannel, "send_message_and_save")

        form = UnifiedIncidentForm()
        form._jira_extra_fields = {}
        form._create_jira_ticket(incident, creator, impacts_data={})

        # The description is enriched for an incident that has a Slack channel
        description = prepare_jira_fields.call_args.kwargs["description"]
        assert description.startswith(incident.description)
        assert f"Incident category: {incident.incident_category.name}" in description
        assert f"Priority: {p1.name}" in description

        # The ticket links back to both the status page and the Slack channel
        links = [
            call.kwargs["object"] for call in jira_client.jira.add_simple_link.call_args_list
        ]
        assert {"url": channel.link, "title": f"Slack conversation #{channel.name}"} in links
        assert any(link["url"] == incident.status_page_url for link in links)

        add_bookmark.assert_called_once_with(
            title="Jira ticket", link=jira_ticket.url, emoji=":jira_new:"
        )
        sent = send_message.call_args.args[0]
        assert isinstance(sent, SlackMessageIncidentDeclaredAnnouncement)
