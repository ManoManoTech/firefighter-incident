from __future__ import annotations

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import IncidentUpdate
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentStatusUpdated,
)


@pytest.mark.django_db
class TestSlackMessageIncidentStatusUpdated:
    """Test SlackMessageIncidentStatusUpdated message generation."""

    def test_title_when_status_mitigated_and_changed(self) -> None:
        """Test that title mentions MITIGATED when incident reaches MITIGATED status.

        Covers line 445: elif incident.status == IncidentStatus.MITIGATED and status_changed:
        """
        # Create an incident in MITIGATED status
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        # Create an IncidentChannel for slack_channel_name
        IncidentChannelFactory.create(incident=incident)

        # Create an IncidentUpdate
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.MITIGATED,
            created_by=user
        )

        # Create the message with status_changed=True and in_channel=False
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=False,
            status_changed=True
        )

        # Verify the title contains "Mitigated" (the status label)
        assert message.title_text is not None
        assert "Mitigated" in message.title_text
        assert ":large_green_circle:" in message.title_text
        assert incident.slack_channel_name in message.title_text

    def test_title_when_status_not_mitigated(self) -> None:
        """Test that title does not use MITIGATED-specific format when status is different."""
        # Create an incident in INVESTIGATING status
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create an IncidentUpdate
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.INVESTIGATING,
            created_by=user
        )

        # Create the message with status_changed=True and in_channel=False
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=False,
            status_changed=True
        )

        # Verify the title does NOT contain the MITIGATED-specific format
        assert message.title_text is not None
        assert ":large_green_circle:" not in message.title_text
        assert "has received an update" in message.title_text


@pytest.mark.django_db
class TestSlackMessageDeployWarning:
    """Test SlackMessageDeployWarning message generation."""

    def test_header_when_incident_mitigated(self) -> None:
        """Test that header includes '(Mitigated)' when incident is MITIGATED.

        Covers line 694: text=f":warning: Deploy warning {'(Mitigated) ' if self.incident.status == IncidentStatus.MITIGATED else ''}:warning:"
        """
        # Create an incident in MITIGATED status
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        # Create an IncidentChannel for conversation.name
        IncidentChannelFactory.create(incident=incident)

        # Create the deploy warning message
        message = SlackMessageDeployWarning(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # The first block should be a HeaderBlock with "(Mitigated)" in the text
        header_block = blocks[0]
        header_text = header_block.text.text  # type: ignore[attr-defined]

        assert "(Mitigated)" in header_text
        assert ":warning:" in header_text

    def test_header_when_incident_not_mitigated(self) -> None:
        """Test that header does NOT include '(Mitigated)' when incident is not MITIGATED."""
        # Create an incident in INVESTIGATING status
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create the deploy warning message
        message = SlackMessageDeployWarning(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # The first block should be a HeaderBlock WITHOUT "(Mitigated)"
        header_block = blocks[0]
        header_text = header_block.text.text  # type: ignore[attr-defined]

        assert "(Mitigated)" not in header_text
        assert ":warning:" in header_text

    def test_additional_blocks_when_incident_mitigated_or_above(self) -> None:
        """Test that additional blocks are added when incident status >= MITIGATED.

        Covers line 705: if self.incident.status >= IncidentStatus.MITIGATED:
        """
        # Create an incident in MITIGATED status
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create the deploy warning message
        message = SlackMessageDeployWarning(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # When status >= MITIGATED, there should be MORE than 2 blocks
        # (HeaderBlock + SectionBlock + additional blocks from line 706)
        assert len(blocks) > 2

    def test_no_additional_blocks_when_incident_below_mitigated(self) -> None:
        """Test that NO additional blocks are added when incident status < MITIGATED."""
        # Create an incident in INVESTIGATING status (below MITIGATED)
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create the deploy warning message
        message = SlackMessageDeployWarning(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # When status < MITIGATED, there should be exactly 2 blocks
        # (HeaderBlock + SectionBlock only, no additional blocks)
        assert len(blocks) == 2
