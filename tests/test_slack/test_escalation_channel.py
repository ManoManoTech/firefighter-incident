"""A P4/P5 incident escalated to P1-P3 gets its Slack channel."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import (
    IncidentChannelFactory,
    SlackConversationFactory,
    SlackUserFactory,
)
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentEscalatedDM,
    SlackMessageIncidentStatusUpdated,
)
from firefighter.slack.models.conversation import Conversation
from firefighter.slack.signals.incident_updated import (
    incident_updated_broadcast_handler,
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
        environment=Environment.objects.get(value="PRD"),
        private=False,
    )


def _escalation_update(incident: Incident, created_by=None) -> IncidentUpdate:
    """The update the Jira priority sync records: no author, the new priority."""
    return IncidentUpdate.objects.create(
        incident=incident,
        priority=incident.priority,
        created_by=created_by,
        message=f"Priority synced from Jira ({incident.priority.value})",
        event_type="jira_priority_sync",
    )


def _escalate(
    incident: Incident,
    *,
    old_priority_value: int = 4,
    created_by=None,
    updated_fields: tuple[str, ...] = ("priority_id",),
    handler=incident_updated_open_channel_on_escalation_handler,
) -> IncidentUpdate:
    incident_update = _escalation_update(incident, created_by)
    handler(
        sender="update_status",
        incident=incident,
        incident_update=incident_update,
        updated_fields=list(updated_fields),
        old_priority=Priority.objects.get(value=old_priority_value),
    )
    return incident_update


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

        update = _escalate(incident, created_by=escalator)

        mock_task.delay.assert_called_once_with(
            incident.id,
            str(escalator.id),
            str(update.id),
            str(Priority.objects.get(value=4).id),
        )

    def test_jira_sync_escalation_has_no_author(self, mock_task):
        incident = _incident()

        _escalate(incident, created_by=None)

        assert mock_task.delay.call_args.args[1] is None

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


@pytest.fixture
def mock_broadcasts():
    with patch(
        "firefighter.slack.signals.incident_updated.publish_broadcasts"
    ) as mocked:
        yield mocked


@pytest.mark.django_db
class TestEscalationBroadcast:
    """The escalation of an incident with no channel is announced once the channel exists."""

    def test_leaves_the_announcement_to_the_channel_opening(self, mock_broadcasts):
        incident = _incident()

        _escalate(incident, handler=incident_updated_broadcast_handler)

        mock_broadcasts.assert_not_called()

    def test_announces_at_once_when_the_incident_already_has_a_channel(
        self, mock_broadcasts
    ):
        incident = _incident()
        IncidentChannelFactory.create(incident=incident)
        incident.refresh_from_db()

        update = _escalate(incident, handler=incident_updated_broadcast_handler)

        mock_broadcasts.assert_called_once()
        assert mock_broadcasts.call_args.kwargs["incident_update"] == update

    def test_announces_other_updates_of_an_incident_without_a_channel(
        self, mock_broadcasts
    ):
        incident = _incident()

        _escalate(
            incident,
            updated_fields=("_status",),
            handler=incident_updated_broadcast_handler,
        )

        mock_broadcasts.assert_called_once()


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


@pytest.fixture
def tech_incidents():
    """The messages posted in any conversation, with a #tech-incidents channel to post in."""
    SlackConversationFactory.create(tag="tech_incidents")
    with patch.object(Conversation, "send_message_and_save", autospec=True) as send:
        yield send


def _announcements(send) -> list[str]:
    """Titles of the incident updates posted in #tech-incidents."""
    return [
        call.args[1].title_text
        for call in send.call_args_list
        if call.args[0].tag == "tech_incidents"
        and isinstance(call.args[1], SlackMessageIncidentStatusUpdated)
    ]


@pytest.mark.django_db
@pytest.mark.usefixtures("channel_opener", "mock_slack", "mock_jira")
class TestEscalationAnnouncement:
    def _open(self, incident: Incident) -> None:
        open_escalated_incident_channel(
            incident.id,
            None,
            str(_escalation_update(incident).id),
            str(Priority.objects.get(value=4).id),
        )

    def test_names_the_new_channel(self, tech_incidents):
        send = tech_incidents
        incident = _incident(priority_value=3)

        self._open(incident)

        channel_name = Incident.objects.get(pk=incident.id).conversation.name
        assert _announcements(send) == [
            f"Incident #{channel_name} has escalated from P4 to P3."
        ]

    def test_is_posted_even_when_the_channel_could_not_be_opened(
        self, tech_incidents, channel_opener
    ):
        send = tech_incidents
        channel_opener.send.side_effect = None
        incident = _incident(priority_value=3)

        self._open(incident)

        assert _announcements(send) == [
            f"Incident #{incident.id} has escalated from P4 to P3."
        ]

    def test_a_task_queued_before_the_deploy_announces_nothing(self, tech_incidents):
        send = tech_incidents
        incident = _incident(priority_value=3)

        open_escalated_incident_channel(incident.id)

        assert _announcements(send) == []

    def test_an_announcement_failure_does_not_prevent_the_dm(self, mock_slack, caplog):
        _, dm = mock_slack
        incident = _incident(priority_value=3)
        with patch(
            "firefighter.slack.signals.incident_updated.publish_broadcasts",
            side_effect=SlackApiError("channel_not_found", {"ok": False}),
        ):
            self._open(incident)

        dm.assert_called_once()
        assert "Could not announce the escalation" in caplog.text

    def test_a_missing_update_is_not_announced(self, tech_incidents, caplog):
        send = tech_incidents
        incident = _incident(priority_value=3)

        open_escalated_incident_channel(
            incident.id, None, "00000000-0000-0000-0000-000000000000", None
        )

        assert _announcements(send) == []
        assert "escalation not announced" in caplog.text


@pytest.mark.django_db
def test_escalation_dm_points_to_the_new_channel():
    incident = _incident()
    channel = IncidentChannelFactory.create(incident=incident)
    incident.refresh_from_db()

    text = SlackMessageIncidentEscalatedDM(incident).get_text()

    assert f"escalated to {incident.priority.name}" in text
    assert f"<#{channel.channel_id}>" in text
