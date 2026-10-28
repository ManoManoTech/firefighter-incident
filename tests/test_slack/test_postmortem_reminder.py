"""The post-mortem reminder is posted whatever the post-mortem backend (Confluence or Jira)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.models import JiraPostMortem
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentPostMortemReminder,
)
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.tasks.reminder_postmortem import publish_postmortem_reminder

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _incident_with_channel() -> Incident:
    incident = IncidentFactory.create(
        priority=Priority.objects.get(name="P1"),
        _status=IncidentStatus.MITIGATED,
    )
    IncidentChannelFactory.create(incident=incident)
    return incident


def _add_jira_postmortem(incident: Incident) -> None:
    JiraPostMortem.objects.create(
        incident=incident,
        jira_issue_key="T2-1",
        jira_issue_id="10001",
        created_by=UserFactory.create(),
    )


@pytest.mark.django_db
class TestPublishPostMortemReminder:
    @staticmethod
    def test_posts_reminder_for_jira_postmortem(mocker: MockerFixture) -> None:
        """Jira-only setups (Confluence disabled) must get the reminder too."""
        incident = _incident_with_channel()
        _add_jira_postmortem(incident)
        send = mocker.patch.object(Conversation, "send_message_and_save")

        publish_postmortem_reminder(incident)

        send.assert_called_once()
        assert isinstance(
            send.call_args.args[0], SlackMessageIncidentPostMortemReminder
        )

    @staticmethod
    def test_posts_reminder_when_postmortem_created_after_lookup(
        mocker: MockerFixture,
    ) -> None:
        """Mirror the mitigation flow: the relation is probed, then the post-mortem is created.

        The miss is cached on the incident by the first lookup; creating the post-mortem
        with incident=incident must refresh that cache, or the reminder is skipped.
        """
        incident = _incident_with_channel()
        assert not hasattr(incident, "jira_postmortem_for")
        _add_jira_postmortem(incident)
        send = mocker.patch.object(Conversation, "send_message_and_save")

        publish_postmortem_reminder(incident)

        send.assert_called_once()

    @staticmethod
    def test_skips_reminder_without_postmortem(
        mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        incident = _incident_with_channel()
        send = mocker.patch.object(Conversation, "send_message_and_save")

        publish_postmortem_reminder(incident)

        send.assert_not_called()
        assert f"incident #{incident.id} with no PostMortem" in caplog.text
