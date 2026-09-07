"""Tests for Slack key event message view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from slack_sdk.models.blocks import InputBlock, SectionBlock

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.timeline import KeyEventsTimelineForm
from firefighter.slack.views.modals import key_event_message
from firefighter.slack.views.modals.key_event_message import KeyEvents

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident


class TestKeyEventMessageForm:
    """The message edits the whole timeline, through the shared form."""

    @staticmethod
    def test_uses_the_prefixed_timeline_form() -> None:
        # Its own action id prefix keeps an edit routing back to this message
        # rather than to the timeline correction one, which renders the same form.
        assert key_event_message.KeyEvents.form_class is KeyEventsTimelineForm
        assert KeyEventsTimelineForm.field_prefix == "key_event_"


@pytest.mark.django_db
class TestKeyEventMessageSignalIntegration:
    """Integration tests verifying signal is sent - covered by test_jira_app tests."""

    # Note: The actual signal sending is tested in:
    # - tests/test_jira_app/test_incident_key_events_sync.py
    # These tests verify the signal handler receives and processes signals correctly.
    # Testing the Slack view's signal sending requires complex Slack mocking,
    # so we rely on manual testing and the signal handler tests instead.


@pytest.mark.django_db
class TestKeyEventMessageBlocks:
    """The Key Events message shows the same timeline preview as the correction one."""

    @staticmethod
    def test_leads_with_the_seven_key_events() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = KeyEvents().build_modal_fn(incident=incident)

        assert isinstance(blocks[0], SectionBlock)
        preview = blocks[0].text.text
        assert preview.startswith("*:stopwatch: Key events*")
        for label in (
            "Started",
            "Detected",
            "Declared",
            "Investigating",
            "Mitigating",
            "Mitigated",
            "Post-mortem",
        ):
            assert f"*{label}*" in preview

    @staticmethod
    def test_labels_are_the_milestone_names_not_their_summaries() -> None:
        """Slack renders input labels as plain text: a summary shows its asterisks."""
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = KeyEvents().build_modal_fn(incident=incident)

        labels = [
            block.label.text
            for block in blocks
            if isinstance(block, InputBlock) and block.label
        ]
        assert labels
        assert "Started" in labels
        assert all("*" not in label for label in labels)
