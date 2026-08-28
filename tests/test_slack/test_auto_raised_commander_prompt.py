"""Tests for the auto-raised-incident Commander prompt.

Incidents raised automatically (which always carry a ``dedup_key``) have no human commander,
so a prompt is posted in the channel asking an invited responder to claim the role. Incidents
declared by a person (no ``dedup_key``) must not get the prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentAutoRaisedCommanderCall,
)
from firefighter.slack.signals.handle_incident_channel_done import (
    prompt_commander_when_auto_raised,
)
from firefighter.slack.views.modals.update_roles import UpdateRolesModal

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.django_db
class TestPromptCommanderWhenAutoRaised:
    @staticmethod
    def _incident_with_channel(dedup_key: str | None):
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(created_by=user, dedup_key=dedup_key)
        incident.save()
        channel = IncidentChannelFactory.build(incident=incident)
        channel.save()
        return incident, channel

    def test_prompts_when_auto_raised(self, mocker: MockerFixture) -> None:
        incident, channel = self._incident_with_channel("mon:1:stock:stg")
        send = mocker.patch.object(channel, "send_message_and_save")

        prompt_commander_when_auto_raised(incident=incident, channel=channel)

        send.assert_called_once()
        posted = send.call_args.args[0]
        assert isinstance(posted, SlackMessageIncidentAutoRaisedCommanderCall)

    def test_skips_when_human_declared(self, mocker: MockerFixture) -> None:
        incident, channel = self._incident_with_channel(None)
        send = mocker.patch.object(channel, "send_message_and_save")

        prompt_commander_when_auto_raised(incident=incident, channel=channel)

        send.assert_not_called()


class TestAutoRaisedCommanderCallMessage:
    """get_blocks is pure (reads incident attrs), so a mocked incident is enough."""

    @staticmethod
    def _incident(usergroup_ids: list[str]) -> MagicMock:
        inc = MagicMock()
        inc.id = 42
        inc.incident_category.usergroups.all.return_value = [
            MagicMock(usergroup_id=uid) for uid in usergroup_ids
        ]
        return inc

    def test_button_uses_update_roles_action(self) -> None:
        blocks = SlackMessageIncidentAutoRaisedCommanderCall(
            self._incident(["S123"])
        ).get_blocks()
        block = blocks[0].to_dict()
        assert block["accessory"]["action_id"] == UpdateRolesModal.open_action
        assert block["accessory"]["value"] == "42"

    def test_mentions_category_usergroups(self) -> None:
        blocks = SlackMessageIncidentAutoRaisedCommanderCall(
            self._incident(["S123", "S456"])
        ).get_blocks()
        text = blocks[0].to_dict()["text"]["text"]
        assert "<!subteam^S123>" in text
        assert "<!subteam^S456>" in text

    def test_no_usergroups_still_prompts(self) -> None:
        blocks = SlackMessageIncidentAutoRaisedCommanderCall(
            self._incident([])
        ).get_blocks()
        text = blocks[0].to_dict()["text"]["text"]
        assert "Commander" in text
        assert "<!subteam" not in text
