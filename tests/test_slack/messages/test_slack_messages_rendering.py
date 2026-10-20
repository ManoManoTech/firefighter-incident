"""Rendering tests for the Slack messages of the incident lifecycle."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, PropertyMock

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, IncidentUpdate, Priority
from firefighter.incidents.models.impact import (
    Impact,
    ImpactLevel,
    ImpactType,
    IncidentImpact,
    LevelChoices,
)
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.jira_app.models import JiraPostMortem, JiraUser
from firefighter.raid.models import JiraTicket
from firefighter.slack.factories import IncidentChannelFactory, MessageFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentComProcess,
    SlackMessageIncidentDeclaredAnnouncement,
    SlackMessageIncidentDeclaredAnnouncementGeneral,
    SlackMessageIncidentDuringOffHours,
    SlackMessageIncidentFixedNextActions,
    SlackMessageIncidentPostMortemCreatedAnnouncement,
    SlackMessageIncidentPostMortemReminder,
    SlackMessageIncidentProcessReminder,
    SlackMessageIncidentProcessReminderAnnouncement,
    SlackMessageIncidentRolesUpdated,
    SlackMessageIncidentStatusUpdated,
    SlackMessageIncidentUpdateReminder,
    SlackMessageRoleAssignedToYou,
    SlackMessagesSOS,
)
from firefighter.slack.views.modals.key_event_message import SlackMessageKeyEvents

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture
    from slack_sdk.models.blocks.blocks import Block


def _blocks_text(blocks: list[Block]) -> str:
    """Flatten every text a list of blocks renders, to assert on what users read."""
    return str([block.to_dict() for block in blocks])


def _incident_with_channel(**kwargs: Any) -> Incident:
    incident: Incident = IncidentFactory.create(**kwargs)
    IncidentChannelFactory.create(incident=incident)
    incident.refresh_from_db()
    return incident


def _add_jira_postmortem(incident: Incident) -> JiraPostMortem:
    return JiraPostMortem.objects.create(
        incident=incident,
        jira_issue_key="PM-42",
        jira_issue_id="4242",
        created_by=UserFactory.create(),
    )


def _add_jira_ticket(incident: Incident) -> JiraTicket:
    jira_user = JiraUser.objects.create(id="jira-user-rendering", user=UserFactory.create())
    return JiraTicket.objects.create(
        id=777, key="INC-777", summary="Ticket", reporter=jira_user, incident=incident
    )


@pytest.fixture
def confluence_postmortem(mocker: MockerFixture) -> MagicMock:
    """A Confluence post-mortem, which the Confluence app (not installed in tests) would return."""
    page = MagicMock(
        page_url="https://confluence.example.com/pm",
        page_edit_url="https://confluence.example.com/pm/edit",
    )
    mocker.patch.object(
        Incident, "confluence_postmortem", new_callable=PropertyMock, return_value=page
    )
    return page


@pytest.mark.django_db
class TestPostMortemReminder:
    @staticmethod
    def test_links_the_confluence_postmortem_and_key_events(
        confluence_postmortem: MagicMock,
    ) -> None:
        incident = _incident_with_channel(_status=IncidentStatus.MITIGATED)
        MessageFactory.create(
            conversation=incident.conversation, ff_type=SlackMessageKeyEvents.id
        )

        message = SlackMessageIncidentPostMortemReminder(incident)
        rendered = _blocks_text(message.get_blocks())

        assert f"Incident #{incident.id}" in message.get_text()
        assert confluence_postmortem.page_edit_url in rendered
        assert "Update key events" in rendered

    @staticmethod
    def test_links_the_jira_postmortem() -> None:
        incident = _incident_with_channel(_status=IncidentStatus.MITIGATED)
        jira_pm = _add_jira_postmortem(incident)
        incident.refresh_from_db()

        rendered = _blocks_text(
            SlackMessageIncidentPostMortemReminder(incident).get_blocks()
        )

        assert "Edit your post-mortem on Jira" in rendered
        assert jira_pm.issue_url in rendered


@pytest.mark.django_db
class TestFixedNextActions:
    @staticmethod
    @pytest.mark.parametrize(
        ("confluence", "jira", "expected"),
        [
            (True, True, " on Confluence or Jira."),
            (True, False, " on Confluence."),
            (False, True, " on Jira."),
        ],
    )
    def test_postmortem_hint_names_the_enabled_services(
        settings: SettingsWrapper, *, confluence: bool, jira: bool, expected: str
    ) -> None:
        settings.ENABLE_CONFLUENCE = confluence
        settings.ENABLE_JIRA_POSTMORTEM = jira
        incident = _incident_with_channel(_status=IncidentStatus.MITIGATED)

        message = SlackMessageIncidentFixedNextActions(incident)

        assert message.get_text() == f"Incident #{incident.id} {incident.status.label}!"
        assert expected in _blocks_text(message.get_blocks())


@pytest.mark.django_db
class TestDeclaredAnnouncement:
    @staticmethod
    def test_shows_jira_ticket_postmortems_and_impacts(
        confluence_postmortem: MagicMock,
    ) -> None:
        incident = _incident_with_channel()
        ticket = _add_jira_ticket(incident)
        jira_pm = _add_jira_postmortem(incident)
        impact_type = ImpactType.objects.create(
            name="Customers", value="customers_rendering", help_text="Customers"
        )
        level = ImpactLevel.objects.create(
            impact_type=impact_type, name="High", value=LevelChoices.HIGH.value
        )
        impact = Impact.objects.create(impact_type=impact_type, impact_level=level)
        IncidentImpact.objects.create(incident=incident, impact=impact)
        incident.refresh_from_db()

        message = SlackMessageIncidentDeclaredAnnouncement(incident)
        rendered = _blocks_text(message.get_blocks())

        assert incident.title in message.get_text()
        assert ticket.url in rendered
        assert confluence_postmortem.page_url in rendered
        assert jira_pm.issue_url in rendered
        assert "*Customers*" in rendered

    @staticmethod
    def test_general_announcement_links_the_jira_ticket() -> None:
        incident = _incident_with_channel()
        ticket = _add_jira_ticket(incident)
        incident.refresh_from_db()

        message = SlackMessageIncidentDeclaredAnnouncementGeneral(incident)
        rendered = _blocks_text(message.get_blocks())

        assert f"#{incident.id}" in message.get_text()
        assert f"#{incident.slack_channel_name}" in rendered
        assert ticket.url in rendered


@pytest.mark.django_db
def test_roles_update_without_changes_says_so() -> None:
    incident = _incident_with_channel()

    message = SlackMessageIncidentRolesUpdated(incident, None)

    assert "_No changes detected._" in _blocks_text(message.get_blocks())


@pytest.mark.django_db
class TestStatusUpdated:
    @staticmethod
    def test_in_channel_update_lists_every_changed_field() -> None:
        incident = _incident_with_channel(_status=IncidentStatus.INVESTIGATING)
        environment = Environment.objects.get(value="PRD")
        update = IncidentUpdate.objects.create(
            incident=incident,
            created_by=UserFactory.create(),
            message="Rolled back",
            title="New title",
            description="New description",
            status=IncidentStatus.INVESTIGATING,
            priority=incident.priority,
            incident_category=incident.incident_category,
            environment=environment,
        )

        message = SlackMessageIncidentStatusUpdated(incident, update)
        rendered = _blocks_text(message.get_blocks())

        assert "New title: *New title*" in rendered
        assert "New description" in rendered
        assert "*Status:*" in rendered
        assert "*Priority:*" in rendered
        assert "*Incident category:*" in rendered
        assert f"*Environment:* {environment.value}" in rendered
        assert message.get_text() == f"Incident #{incident.id} has received an update."
        assert message.get_metadata().event_payload == {
            "incident_id": incident.id,
            "incident_update_id": str(update.id),
        }
        assert message.get_slack_message_options() == {"unfurl_links": False}

    @staticmethod
    def test_title_announces_an_escalation_from_p4() -> None:
        incident = _incident_with_channel(
            _status=IncidentStatus.INVESTIGATING,
            priority=Priority.objects.get(value=2),
        )
        update = IncidentUpdate.objects.create(
            incident=incident, created_by=UserFactory.create()
        )

        message = SlackMessageIncidentStatusUpdated(
            incident,
            update,
            in_channel=False,
            old_priority=Priority.objects.get(value=4),
        )

        assert message.title_text == (
            f"Incident #{incident.slack_channel_name} has escalated from P4 to P2."
        )


@pytest.mark.django_db
class TestPostMortemAnnouncementsAndReminders:
    @staticmethod
    def test_postmortem_created_announcement_links_the_jira_postmortem() -> None:
        incident = _incident_with_channel()
        jira_pm = _add_jira_postmortem(incident)
        incident.refresh_from_db()

        message = SlackMessageIncidentPostMortemCreatedAnnouncement(incident)

        assert f"#{incident.id}" in message.get_text()
        assert jira_pm.issue_url in _blocks_text(message.get_blocks())

    @staticmethod
    def test_process_reminder_links_both_postmortems(
        confluence_postmortem: MagicMock,
    ) -> None:
        incident = _incident_with_channel(_status=IncidentStatus.MITIGATED)
        jira_pm = _add_jira_postmortem(incident)
        incident.refresh_from_db()

        rendered = _blocks_text(
            SlackMessageIncidentProcessReminder(
                incident, stale_for=timedelta(days=3)
            ).get_blocks()
        )

        assert "Open Post-Mortem (Confluence)" in rendered
        assert confluence_postmortem.page_edit_url in rendered
        assert jira_pm.issue_url in rendered

    @staticmethod
    def test_process_reminder_announcement_links_the_jira_postmortem() -> None:
        incident = _incident_with_channel(
            _status=IncidentStatus.MITIGATED, mitigated_at=timezone.now()
        )
        jira_pm = _add_jira_postmortem(incident)
        incident.refresh_from_db()

        message = SlackMessageIncidentProcessReminderAnnouncement(incident)

        assert f"#{incident.id}" in message.get_text()
        assert jira_pm.issue_url in _blocks_text(message.get_blocks())


@pytest.mark.django_db
def test_off_hours_message_points_to_the_oncall_page(mocker: MockerFixture) -> None:
    # The PagerDuty URLs are only registered when the PagerDuty app is enabled
    reverse = mocker.patch(
        "firefighter.slack.messages.slack_messages.reverse", return_value="/oncall/"
    )
    message = SlackMessageIncidentDuringOffHours()

    rendered = _blocks_text(message.get_blocks())

    assert "/incident oncall" in message.get_text()
    reverse.assert_called_once_with("pagerduty:oncall-list")
    assert "Incident during out of office hours" in rendered
    assert "/oncall/" in rendered


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("priority_value", "expected"),
    [
        (4, "You may want to update this incident."),
        (2, "You need to update this incident to broadcast information"),
    ],
)
def test_update_reminder_depends_on_the_priority(
    priority_value: int, expected: str
) -> None:
    incident = _incident_with_channel(
        priority=Priority.objects.get(value=priority_value)
    )

    message = SlackMessageIncidentUpdateReminder(incident, "2 hours")

    assert "Reminder to update this incident" in message.get_text()
    rendered = _blocks_text(message.get_blocks())
    assert expected in rendered
    assert "no update for 2 hours" in rendered


@pytest.mark.django_db
@pytest.mark.parametrize("usergroup_id", [None, "S0EMERGENCY"])
def test_com_process_mentions_the_emergency_usergroup_when_configured(
    mocker: MockerFixture, usergroup_id: str | None
) -> None:
    mocker.patch(
        "firefighter.slack.messages.slack_messages.SLACK_EMERGENCY_USERGROUP_ID",
        usergroup_id,
    )
    incident = _incident_with_channel(priority=Priority.objects.get(value=1))

    message = SlackMessageIncidentComProcess(incident)
    rendered = _blocks_text(message.get_blocks())

    assert message.get_text() == "Follow the communication process for P1 incidents."
    assert ("<!subteam^S0EMERGENCY>" in rendered) is (usergroup_id is not None)


@pytest.mark.django_db
def test_deploy_warning_text_asks_to_refrain_from_deploying() -> None:
    incident = _incident_with_channel()

    text = SlackMessageDeployWarning(incident).get_text()

    assert "refrain to deploy until it's resolved" in text


@pytest.mark.django_db
def test_sos_message_names_the_usergroup_and_the_incident() -> None:
    incident = _incident_with_channel()

    message = SlackMessagesSOS(incident, "@backend-team")

    assert message.get_text() == (
        f"Hello @backend-team, we need your help on {incident.priority.name} incident {incident.conversation.name}."
    )
    assert "Hello @backend-team" in _blocks_text(message.get_blocks())


@pytest.mark.django_db
@pytest.mark.parametrize("first_update", [True, False])
def test_role_assigned_to_you_explains_automatic_assignment_on_creation(
    *, first_update: bool
) -> None:
    incident = _incident_with_channel()
    role_type, _ = IncidentRoleType.objects.get_or_create(
        slug="commander",
        defaults={
            "name": "Commander",
            "summary": "Drives the incident",
            "description": "Commander role",
            "required": True,
        },
    )

    message = SlackMessageRoleAssignedToYou(
        incident, role_type, first_update=first_update
    )
    rendered = _blocks_text(message.get_blocks())

    assert message.get_text() == (
        f"You have been assigned the {role_type.name} role on incident #{incident.conversation.name}."
    )
    assert f"You have been assigned the {role_type.name} role" in rendered
    assert ("because you created the incident" in rendered) is (
        first_update and role_type.required
    )
