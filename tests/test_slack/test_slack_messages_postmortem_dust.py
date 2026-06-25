from __future__ import annotations

import pytest
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import SectionBlock

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.models import JiraPostMortem
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentPostMortemCreated,
)


def _make_incident_with_jira_pm() -> object:
    user = UserFactory.build()
    user.save()
    incident = IncidentFactory.build(created_by=user)
    incident.save()
    JiraPostMortem.objects.create(
        incident=incident,
        jira_issue_key="INCIDENT-123",
        jira_issue_id="10001",
        created_by=user,
    )
    incident.refresh_from_db()
    return incident


def _get_button_action_ids(blocks: list) -> list[str]:
    return [
        block.accessory.action_id
        for block in blocks
        if isinstance(block, SectionBlock)
        and isinstance(getattr(block, "accessory", None), ButtonElement)
    ]


@pytest.mark.django_db
def test_dust_button_present_when_setting_configured(settings) -> None:
    """Button appears when DUST_SLACK_BOT_USER_ID is set and JIRA post-mortem exists."""
    settings.DUST_SLACK_BOT_USER_ID = "UDUSTBOT1"
    incident = _make_incident_with_jira_pm()

    msg = SlackMessageIncidentPostMortemCreated(incident)
    blocks = msg.get_blocks()

    action_ids = _get_button_action_ids(blocks)
    assert "generate_dust_postmortem" in action_ids

    dust_block = next(
        b for b in blocks
        if isinstance(b, SectionBlock)
        and isinstance(getattr(b, "accessory", None), ButtonElement)
        and b.accessory.action_id == "generate_dust_postmortem"
    )
    assert dust_block.accessory.value == str(incident.id)


@pytest.mark.django_db
def test_dust_button_absent_when_setting_not_configured(settings) -> None:
    """Button is absent when DUST_SLACK_BOT_USER_ID is not set."""
    settings.DUST_SLACK_BOT_USER_ID = None
    incident = _make_incident_with_jira_pm()

    msg = SlackMessageIncidentPostMortemCreated(incident)
    blocks = msg.get_blocks()

    action_ids = _get_button_action_ids(blocks)
    assert "generate_dust_postmortem" not in action_ids
