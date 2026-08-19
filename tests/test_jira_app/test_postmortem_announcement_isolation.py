"""Tests that a failing post-mortem announcement does not drop the reminder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.test import override_settings
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.models.incident_channel import IncidentChannel

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

HANDLER = "firefighter.jira_app.signals.postmortem_created"
REMINDER = "firefighter.slack.tasks.reminder_postmortem.publish_postmortem_reminder"


@pytest.mark.django_db
class TestPostMortemAnnouncementIsolation:
    """The #critical-incidents announcement must not abort the rest of the handler."""

    @staticmethod
    @override_settings(ENABLE_JIRA_POSTMORTEM=True)
    def test_reminder_still_published_when_announcement_fails(
        mocker: MockerFixture,
    ) -> None:
        """A dead broadcast channel must not swallow the post-mortem reminder."""
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(
            priority=Priority.objects.get(name="P1"),
            environment=Environment.objects.get(value="PRD"),
            created_by=user,
            private=False,
            _status=IncidentStatus.MITIGATING,
        )
        incident.save()
        IncidentChannelFactory.build(incident=incident).save()

        mocker.patch.object(IncidentChannel, "rename_if_needed")
        mocker.patch.object(IncidentChannel, "set_incident_channel_topic")
        mocker.patch.object(Conversation, "send_message_and_save")
        mocker.patch(f"{HANDLER}._create_jira_postmortem", return_value=object())
        mocker.patch(
            f"{HANDLER}._publish_postmortem_announcement",
            side_effect=SlackApiError(
                "channel_not_found", response={"error": "channel_not_found"}
            ),
        )
        mock_reminder = mocker.patch(REMINDER)

        incident.create_incident_update(created_by=user, status=IncidentStatus.MITIGATED)

        mock_reminder.assert_called_once()
