"""Tests for the Update menu, and the timeline correction entry it carries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from slack_sdk.models.blocks.blocks import ActionsBlock

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.views.modals.review_timeline import (
    OPEN_TIMELINE_CORRECTION_ACTION_ID,
)
from firefighter.slack.views.modals.update import UpdateModal

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident


def _action_ids(incident: Incident) -> list[str]:
    view = UpdateModal().build_modal_fn(incident=incident)
    return [
        element.action_id
        for block in view.blocks
        if isinstance(block, ActionsBlock)
        for element in block.elements
    ]


@pytest.mark.django_db
class TestUpdateModalFixTimeline:
    @staticmethod
    def test_offered_in_post_mortem() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        IncidentChannelFactory.create(incident=incident)

        assert OPEN_TIMELINE_CORRECTION_ACTION_ID in _action_ids(incident)

    @staticmethod
    def test_not_offered_before_the_review_checkpoint() -> None:
        # The timeline is still being recorded by the normal status updates.
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)

        assert OPEN_TIMELINE_CORRECTION_ACTION_ID not in _action_ids(incident)

    @staticmethod
    def test_not_offered_once_closed() -> None:
        # Metrics and post-mortem are consolidated; late edits go through the admin.
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.CLOSED)
        IncidentChannelFactory.create(incident=incident)

        assert OPEN_TIMELINE_CORRECTION_ACTION_ID not in _action_ids(incident)

    @staticmethod
    def test_not_offered_without_a_channel() -> None:
        # P4/P5 incidents have no conversation to post the correction message in.
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)

        assert OPEN_TIMELINE_CORRECTION_ACTION_ID not in _action_ids(incident)

    @staticmethod
    def test_keeps_the_existing_entries() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        IncidentChannelFactory.create(incident=incident)

        assert len(_action_ids(incident)) == 4
