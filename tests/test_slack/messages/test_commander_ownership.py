"""The Commander is told, at every step, that they own driving the process to closure."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import (
    COMMANDER_ROLE_SLUG,
    IncidentRoleType,
)
from firefighter.incidents.models.priority import Priority
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentFixedNextActions,
    SlackMessageIncidentPostMortemReminder,
    SlackMessageIncidentProcessReminder,
    SlackMessageIncidentRolesUpdated,
)

COMMANDER_SLACK_ID = "U0COMMANDER"


def _incident(priority_value: int, *, with_commander: bool = True) -> Incident:
    incident = IncidentFactory.create(
        _status=IncidentStatus.MITIGATED,
        priority=Priority.objects.get(value=priority_value),
        environment=Environment.objects.get(value="PRD"),
        mitigated_at=timezone.now() - timedelta(days=6),
    )
    # The reminders look for a Confluence post-mortem. The Confluence models are importable even
    # when the app is disabled, so the lookup would hit a table the test database never creates.
    # Priming the cache with "no related object" stands in for a deployment without Confluence.
    incident._state.fields_cache["postmortem_for"] = None
    IncidentChannelFactory.create(incident=incident)
    if with_commander:
        user = UserFactory.create()
        SlackUserFactory.create(user=user, slack_id=COMMANDER_SLACK_ID)
        IncidentRole.objects.create(
            incident=incident,
            user=user,
            role_type=IncidentRoleType.objects.get(slug=COMMANDER_ROLE_SLUG),
        )
    return incident


@pytest.mark.django_db
class TestCommanderOwnershipAtOpening:
    def test_roles_message_names_the_commander_and_their_ownership(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert f"<@{COMMANDER_SLACK_ID}>" in blocks_text
        assert "you are the *Incident Commander*" in blocks_text
        assert "you lead the process through to closure" in blocks_text
        assert "post-mortem is carried out before the incident is closed" in blocks_text

    def test_roles_message_invites_a_hand_over_to_a_more_suitable_responder(self):
        incident = _incident(2)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert "Not the right person for a role?" in blocks_text
        assert "Talk it over in this channel" in blocks_text
        assert "with their agreement" in blocks_text

    def test_ownership_is_stated_for_p3(self):
        incident = _incident(3)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert "you are the *Incident Commander*" in blocks_text

    def test_ownership_is_not_stated_for_p4_which_has_no_such_process(self):
        incident = _incident(4)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert "Incident Commander*" not in blocks_text
        assert "Not the right person for a role?" not in blocks_text

    def test_ownership_is_not_repeated_on_later_role_updates(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident,
                incident_update=None,
                first_update=False,
                updated_fields=["commander"],
            ).get_blocks()
        )

        assert "you lead the process through to closure" not in blocks_text

    def test_unassigned_command_is_called_out_instead_of_a_mention(self):
        incident = _incident(1, with_commander=False)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert "No *Incident Commander* is assigned" in blocks_text
        assert f"<@{COMMANDER_SLACK_ID}>" not in blocks_text

    def test_roles_guide_is_linked_when_configured(self, settings):
        settings.SLACK_ROLES_GUIDE_URL = "https://example.test/roles"
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentRolesUpdated(
                incident=incident, incident_update=None, first_update=True
            ).get_blocks()
        )

        assert "https://example.test/roles|Your role in detail" in blocks_text


@pytest.mark.django_db
class TestCommanderOwnershipAtMitigation:
    def test_postmortem_reminder_puts_the_post_mortem_on_the_commander(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentPostMortemReminder(incident).get_blocks()
        )

        assert f"<@{COMMANDER_SLACK_ID}>" in blocks_text
        assert "it's on you to organize the post-mortem" in blocks_text

    def test_next_actions_puts_key_events_and_closure_on_the_commander(self):
        incident = _incident(3)

        blocks_text = str(
            SlackMessageIncidentFixedNextActions(incident).get_blocks()
        )

        assert f"<@{COMMANDER_SLACK_ID}>" in blocks_text
        assert "key events submitted" in blocks_text


@pytest.mark.django_db
class TestProcessReminderMessage:
    def test_asks_for_the_post_mortem_when_the_priority_requires_one(self, settings):
        settings.ENABLE_JIRA_POSTMORTEM = True
        incident = _incident(1)

        message = SlackMessageIncidentProcessReminder(incident)
        blocks_text = str(message.get_blocks())

        assert "The post-mortem *must* be completed" in blocks_text
        assert "it's on you to organize the post-mortem" in blocks_text
        assert "post-mortem" in message.get_text()

    def test_asks_for_key_events_and_closure_when_no_post_mortem_is_required(
        self, settings
    ):
        settings.ENABLE_JIRA_POSTMORTEM = True
        incident = _incident(3)

        message = SlackMessageIncidentProcessReminder(incident)
        blocks_text = str(message.get_blocks())

        assert "The key events *must* be submitted" in blocks_text
        assert "key events submitted" in blocks_text
        assert "still has to be closed" in message.get_text()

    def test_states_how_long_the_incident_has_been_mitigated(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentProcessReminder(incident).get_blocks()
        )

        assert "This incident has been mitigated for" in blocks_text

    def test_states_how_long_the_process_has_been_still_on_a_repeat(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentProcessReminder(
                incident, stale_for=timedelta(days=3)
            ).get_blocks()
        )

        assert "The process has not moved for" in blocks_text

    def test_offers_to_hand_command_over(self):
        incident = _incident(1)

        blocks_text = str(
            SlackMessageIncidentProcessReminder(incident).get_blocks()
        )

        assert "Still the right owner?" in blocks_text
        assert "Update roles" in blocks_text
        assert "with their agreement" in blocks_text
