"""A P4/P5 incident escalated to P1-P3 gets its Slack channel."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.messages.slack_messages import SlackMessageIncidentEscalatedDM
from firefighter.slack.signals.incident_updated import (
    incident_updated_open_channel_on_escalation_handler,
)
from firefighter.slack.tasks.open_escalated_incident_channel import (
    open_escalated_incident_channel,
)

TASK = "firefighter.slack.tasks.open_escalated_incident_channel"


def _incident(
    *, priority_value: int = 2, status: int = IncidentStatus.INVESTIGATING.value
) -> Incident:
    declarer = UserFactory.create()
    SlackUserFactory.create(user=declarer)
    return IncidentFactory.create(
        priority=Priority.objects.get(value=priority_value),
        _status=status,
        created_by=declarer,
    )


def _escalate(
    incident: Incident,
    *,
    old_priority_value: int = 4,
    created_by=None,
    updated_fields: tuple[str, ...] = ("priority_id",),
) -> None:
    incident_update = MagicMock(created_by_id=created_by.id if created_by else None)
    incident_updated_open_channel_on_escalation_handler(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=list(updated_fields),
        old_priority=Priority.objects.get(value=old_priority_value),
    )


@pytest.fixture
def mock_task():
    with patch(
        "firefighter.slack.signals.incident_updated.open_escalated_incident_channel"
    ) as mocked:
        yield mocked


@pytest.mark.django_db
class TestEscalationReceiver:
    def test_opens_the_channel_of_an_escalated_incident(self, mock_task):
        incident = _incident()
        escalator = UserFactory.create()

        _escalate(incident, created_by=escalator)

        mock_task.delay.assert_called_once_with(incident.id, str(escalator.id))

    def test_jira_sync_escalation_has_no_author(self, mock_task):
        incident = _incident()

        _escalate(incident, created_by=None)

        mock_task.delay.assert_called_once_with(incident.id, None)

    @pytest.mark.parametrize(
        ("old_priority_value", "new_priority_value"),
        [(2, 1), (4, 5)],
        ids=["already-critical", "stays-normal"],
    )
    def test_ignores_changes_that_are_not_an_escalation(
        self, mock_task, old_priority_value, new_priority_value
    ):
        incident = _incident(priority_value=new_priority_value)

        _escalate(incident, old_priority_value=old_priority_value)

        mock_task.delay.assert_not_called()

    def test_ignores_an_incident_that_already_has_a_channel(self, mock_task):
        incident = _incident()
        IncidentChannelFactory.create(incident=incident)
        incident.refresh_from_db()

        _escalate(incident)

        mock_task.delay.assert_not_called()

    def test_ignores_an_incident_past_mitigation(self, mock_task):
        incident = _incident(status=IncidentStatus.POST_MORTEM.value)

        _escalate(incident)

        mock_task.delay.assert_not_called()

    def test_ignores_updates_that_do_not_change_the_priority(self, mock_task):
        incident = _incident()

        _escalate(incident, updated_fields=("_status",))

        mock_task.delay.assert_not_called()


@pytest.fixture(autouse=True)
def _local_memory_cache(settings):
    """The task locks through the default cache: isolate it from Redis and between tests."""
    settings.CACHES = {
        **settings.CACHES,
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    }
    from django.core.cache import caches

    caches["default"].clear()


@pytest.fixture
def channel_opener():
    """Stand in for the declaration flow: the signal creates the incident channel."""

    def _open(_sender, *, incident, **_kwargs):
        IncidentChannelFactory.create(incident=incident)

    with patch(f"{TASK}.create_incident_conversation") as signal:
        signal.send.side_effect = _open
        yield signal


@pytest.fixture
def mock_slack():
    with (
        patch("firefighter.slack.models.incident_channel.IncidentChannel.invite_users") as invite,
        patch("firefighter.slack.models.user.SlackUser.send_private_message") as dm,
    ):
        yield invite, dm


@pytest.fixture
def mock_jira():
    with patch("firefighter.raid.client.client") as jira:
        yield jira


def _dm_recipients(dm) -> set:
    return {
        call.args[0].incident.id
        for call in dm.call_args_list
        if isinstance(call.args[0], SlackMessageIncidentEscalatedDM)
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("channel_opener", "mock_slack", "mock_jira")
class TestOpenEscalatedIncidentChannel:
    def test_opens_the_channel_without_the_declared_announcements(self, channel_opener):
        incident = _incident()

        open_escalated_incident_channel(incident.id)

        channel_opener.send.assert_called_once()
        assert channel_opener.send.call_args.kwargs["announce_globally"] is False

    def test_comments_the_jira_ticket_with_the_channel(self, mock_jira, settings):
        settings.ENABLE_RAID = True
        incident = _incident()
        jira_ticket = MagicMock(id=42)
        with patch.object(Incident, "jira_ticket", jira_ticket, create=True):
            open_escalated_incident_channel(incident.id)

        (issue_id, body), _ = mock_jira.add_comment.call_args
        assert issue_id == 42
        assert "escalated to P2" in body

    def test_dms_the_declarer_and_invites_and_dms_the_escalator(self, mock_slack):
        invite, dm = mock_slack
        incident = _incident()
        escalator = UserFactory.create()
        SlackUserFactory.create(user=escalator)

        open_escalated_incident_channel(incident.id, str(escalator.id))

        assert invite.call_args.args[0] == [escalator]
        assert dm.call_count == 2
        assert _dm_recipients(dm) == {incident.id}

    def test_a_jira_failure_does_not_prevent_the_dm(self, mock_slack, mock_jira, settings):
        settings.ENABLE_RAID = True
        _, dm = mock_slack
        mock_jira.add_comment.side_effect = RuntimeError("Jira down")
        incident = _incident()
        with patch.object(Incident, "jira_ticket", MagicMock(id=42), create=True):
            open_escalated_incident_channel(incident.id)

        dm.assert_called_once()

    def test_opens_a_single_channel_for_two_escalations(self, channel_opener):
        incident = _incident()

        open_escalated_incident_channel(incident.id)
        open_escalated_incident_channel(incident.id)

        channel_opener.send.assert_called_once()

    def test_does_nothing_when_the_incident_already_has_a_channel(self, channel_opener):
        incident = _incident()
        IncidentChannelFactory.create(incident=incident)

        open_escalated_incident_channel(incident.id)

        channel_opener.send.assert_not_called()

    def test_tells_nobody_when_the_channel_could_not_be_opened(self, channel_opener, mock_slack, mock_jira):
        _, dm = mock_slack
        channel_opener.send.side_effect = None
        incident = _incident()

        open_escalated_incident_channel(incident.id)

        dm.assert_not_called()
        mock_jira.add_comment.assert_not_called()

    def test_skips_people_without_a_slack_account(self, mock_slack):
        _, dm = mock_slack
        incident = _incident()
        escalator_without_slack = UserFactory.create()

        open_escalated_incident_channel(incident.id, str(escalator_without_slack.id))

        dm.assert_called_once()

    def test_a_dm_failure_does_not_fail_the_task(self, mock_slack, caplog):
        _, dm = mock_slack
        dm.side_effect = SlackApiError("cannot_dm_bot", {"ok": False})
        incident = _incident()

        open_escalated_incident_channel(incident.id)

        dm.assert_called_once()
        assert [r.levelno for r in caplog.records if "Could not DM" in r.getMessage()] == [
            logging.ERROR
        ]

    def test_dms_turned_off_by_the_user_only_warn(self, mock_slack, caplog):
        _, dm = mock_slack
        dm.side_effect = SlackApiError(
            "messages_tab_disabled", {"ok": False, "error": "messages_tab_disabled"}
        )
        incident = _incident()

        open_escalated_incident_channel(incident.id)

        dm.assert_called_once()
        assert "has disabled private messages from bots" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.django_db
def test_escalation_dm_points_to_the_new_channel():
    incident = _incident()
    channel = IncidentChannelFactory.create(incident=incident)
    incident.refresh_from_db()

    text = SlackMessageIncidentEscalatedDM(incident).get_text()

    assert f"escalated to {incident.priority.name}" in text
    assert f"<#{channel.channel_id}>" in text
