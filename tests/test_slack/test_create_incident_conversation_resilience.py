"""Tests for the resilience of the create_incident_conversation signal handler.

When ancillary Slack calls fail (e.g. announcement in #tech-incidents or
#it-deploy points at a channel ID that does not exist in the current
workspace), the handler must log the error and keep going so that the
response team invite and downstream signals still run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.signals.create_incident_conversation import (
    create_incident_slack_conversation,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _build_incident_with_channel() -> tuple[object, object]:
    user = UserFactory.build()
    user.save()
    SlackUserFactory.create(user=user)
    # Pin the priority and the environment: the factory draws them from
    # session-wide cyclic iterators, so an unpinned incident lands on P1/PRD
    # depending on the test order, and sev1_process_reminder then posts a
    # second message in the channel these tests count the messages of.
    incident = IncidentFactory.build(
        created_by=user,
        priority=Priority.objects.get(value=3),
        environment=Environment.objects.get(value="STG"),
    )
    incident.save()
    incident_channel = IncidentChannelFactory.build(incident=incident)
    incident_channel.save()
    incident.refresh_from_db()
    return incident, incident_channel


def _patch_handler_dependencies(
    mocker: MockerFixture,
    *,
    tech_conv: object | None,
    it_deploy_conv: object | None,
    publish_general: bool = True,
    publish_it_deploy: bool = True,
) -> MagicMock:
    """Replace every external call the handler makes with a controlled mock.

    Returns the MagicMock that stands in for the freshly created incident channel.
    """
    new_channel = MagicMock()
    new_channel.channel_id = "C-NEW-INCIDENT"
    new_channel.conversations_join.return_value = None
    new_channel.set_incident_channel_topic.return_value = None
    new_channel.invite_users.return_value = None
    new_channel.send_message_and_save.return_value = None

    mocker.patch(
        "firefighter.slack.signals.create_incident_conversation.IncidentChannel.objects.create_incident_channel",
        return_value=new_channel,
    )
    mocker.patch(
        "firefighter.slack.signals.create_incident_conversation.should_publish_in_general_channel",
        return_value=publish_general,
    )
    mocker.patch(
        "firefighter.slack.signals.create_incident_conversation.should_publish_in_it_deploy_channel",
        return_value=publish_it_deploy,
    )

    def _lookup(tag: str) -> object | None:
        return {"tech_incidents": tech_conv, "it_deploy": it_deploy_conv}.get(tag)

    mocker.patch(
        "firefighter.slack.signals.create_incident_conversation.Conversation.objects.get_or_none",
        side_effect=_lookup,
    )
    return new_channel


@pytest.mark.django_db
class TestCreateIncidentSlackConversationResilience:
    """Verify ancillary Slack failures do not abort the handler."""

    @staticmethod
    def test_tech_incidents_send_failure_does_not_abort_flow(
        mocker: MockerFixture,
    ) -> None:
        incident, _ = _build_incident_with_channel()
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch.object(incident.conversation, "invite_users")

        tech_conv = MagicMock()
        tech_conv.channel_id = "C-TECH"
        tech_conv.send_message_and_save.side_effect = SlackApiError(
            "channel_not_found", response={}
        )
        it_deploy_conv = MagicMock()
        it_deploy_conv.channel_id = "C-DEPLOY"
        it_deploy_conv.send_message_and_save.return_value = None

        _patch_handler_dependencies(
            mocker, tech_conv=tech_conv, it_deploy_conv=it_deploy_conv
        )

        create_incident_slack_conversation(incident=incident)

        tech_conv.send_message_and_save.assert_called_once()
        it_deploy_conv.send_message_and_save.assert_called_once()
        incident.conversation.invite_users.assert_called_once()

    @staticmethod
    def test_it_deploy_send_failure_does_not_abort_flow(mocker: MockerFixture) -> None:
        incident, _ = _build_incident_with_channel()
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch.object(incident.conversation, "invite_users")

        tech_conv = MagicMock()
        tech_conv.channel_id = "C-TECH"
        tech_conv.send_message_and_save.return_value = None
        it_deploy_conv = MagicMock()
        it_deploy_conv.channel_id = "C-DEPLOY"
        it_deploy_conv.send_message_and_save.side_effect = SlackApiError(
            "channel_not_found", response={}
        )

        signal_seen: list[object] = []
        from firefighter.slack.signals import incident_channel_done

        def _capture(**kwargs: object) -> None:
            signal_seen.append(kwargs)

        incident_channel_done.connect(_capture, weak=False)
        try:
            _patch_handler_dependencies(
                mocker, tech_conv=tech_conv, it_deploy_conv=it_deploy_conv
            )
            create_incident_slack_conversation(incident=incident)
        finally:
            incident_channel_done.disconnect(_capture)

        it_deploy_conv.send_message_and_save.assert_called_once()
        assert signal_seen, "incident_channel_done must still be fired after it_deploy failure"

    @staticmethod
    def test_announcement_send_failure_does_not_abort_flow(
        mocker: MockerFixture,
    ) -> None:
        incident, _ = _build_incident_with_channel()
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch.object(incident.conversation, "invite_users")

        tech_conv = MagicMock()
        tech_conv.channel_id = "C-TECH"
        tech_conv.send_message_and_save.return_value = None
        it_deploy_conv = MagicMock()
        it_deploy_conv.channel_id = "C-DEPLOY"
        it_deploy_conv.send_message_and_save.return_value = None

        new_channel = _patch_handler_dependencies(
            mocker, tech_conv=tech_conv, it_deploy_conv=it_deploy_conv
        )
        new_channel.send_message_and_save.side_effect = SlackApiError(
            "rate_limited", response={}
        )

        create_incident_slack_conversation(incident=incident)

        new_channel.send_message_and_save.assert_called_once()
        tech_conv.send_message_and_save.assert_called_once()
        it_deploy_conv.send_message_and_save.assert_called_once()


@pytest.mark.django_db
class TestCreateIncidentSlackConversationBranches:
    """Degraded paths that must stop early or only log a warning."""

    @staticmethod
    def test_missing_channel_id_stops_the_flow(mocker: MockerFixture) -> None:
        incident, _ = _build_incident_with_channel()
        new_channel = _patch_handler_dependencies(
            mocker, tech_conv=None, it_deploy_conv=None
        )
        new_channel.channel_id = ""

        assert create_incident_slack_conversation(incident=incident) is None

        new_channel.conversations_join.assert_not_called()
        new_channel.send_message_and_save.assert_not_called()

    @staticmethod
    def test_opener_invite_failure_does_not_abort_flow(
        mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        incident, _ = _build_incident_with_channel()
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch.object(incident.conversation, "invite_users")
        new_channel = _patch_handler_dependencies(
            mocker, tech_conv=None, it_deploy_conv=None, publish_general=False, publish_it_deploy=False
        )
        new_channel.invite_users.side_effect = SlackApiError(
            "cant_invite", response={}
        )

        create_incident_slack_conversation(incident=incident)

        assert "Could not import Slack opener user!" in caplog.text
        new_channel.send_message_and_save.assert_called_once()
        incident.conversation.invite_users.assert_called_once()

    @staticmethod
    def test_missing_announcement_channels_only_warn(
        mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        incident, _ = _build_incident_with_channel()
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch.object(incident.conversation, "invite_users")
        _patch_handler_dependencies(mocker, tech_conv=None, it_deploy_conv=None)

        create_incident_slack_conversation(incident=incident)

        assert "Could not find tech_incidents conversation!" in caplog.text
        assert "Could not find it_deploy conversation!" in caplog.text
        incident.conversation.invite_users.assert_called_once()


@pytest.mark.django_db
def test_escalation_channel_skips_the_declared_announcements(
    mocker: MockerFixture,
) -> None:
    """An escalation is already broadcast as an update: no "declared" announcement on top."""
    incident, _ = _build_incident_with_channel()
    mocker.patch.object(incident, "build_invite_list", return_value=[])
    mocker.patch.object(incident.conversation, "invite_users")
    tech_conv = MagicMock()
    it_deploy_conv = MagicMock()
    _patch_handler_dependencies(mocker, tech_conv=tech_conv, it_deploy_conv=it_deploy_conv)

    create_incident_slack_conversation(incident=incident, announce_globally=False)

    tech_conv.send_message_and_save.assert_not_called()
    it_deploy_conv.send_message_and_save.assert_not_called()
    incident.conversation.invite_users.assert_called_once()
