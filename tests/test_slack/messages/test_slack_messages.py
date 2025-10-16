from __future__ import annotations

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import IncidentUpdate
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentDeclaredAnnouncement,
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

    def test_no_update_button_when_incident_closed(self) -> None:
        """Test that Update Status button is NOT displayed when incident is CLOSED.

        This prevents showing an action button in an archived channel.
        """
        # Create an incident in CLOSED status
        incident = IncidentFactory.create(_status=IncidentStatus.CLOSED)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create an IncidentUpdate with status change
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            status=IncidentStatus.CLOSED,
            created_by=user
        )

        # Create the message with in_channel=True (normal case for in-channel messages)
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=True,
            status_changed=True
        )

        # Get the blocks
        blocks = message.get_blocks()

        # Find any SectionBlock with the "message_status_update" block_id
        status_update_block = None
        for block in blocks:
            if hasattr(block, "block_id") and block.block_id == "message_status_update":
                status_update_block = block
                break

        # If there is a status update block, verify it has NO accessory (button)
        if status_update_block:
            assert status_update_block.accessory is None, "Update button should not be present when incident is CLOSED"

    def test_update_button_shown_when_incident_not_closed(self) -> None:
        """Test that Update Status button IS displayed when incident is NOT CLOSED."""
        # Create an incident in INVESTIGATING status (not closed)
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

        # Create the message with in_channel=True
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=True,
            status_changed=True
        )

        # Get the blocks
        blocks = message.get_blocks()

        # Find the SectionBlock with "message_status_update" block_id
        status_update_block = None
        for block in blocks:
            if hasattr(block, "block_id") and block.block_id == "message_status_update":
                status_update_block = block
                break

        # Verify the block has an accessory (Update button)
        assert status_update_block is not None, "Should have a status update block"
        assert status_update_block.accessory is not None, "Update button should be present when incident is not CLOSED"
        assert status_update_block.accessory.text.text == "Update"


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


@pytest.mark.django_db
class TestSlackMessageIncidentDeclaredAnnouncement:
    """Test SlackMessageIncidentDeclaredAnnouncement message with custom fields."""

    def test_custom_fields_displayed_when_present(self) -> None:
        """Test that custom fields are displayed in the incident announcement."""
        # Create an incident with custom fields
        incident = IncidentFactory.create(
            custom_fields={
                "zendesk_ticket_id": "12345",
                "seller_contract_id": "SELLER-67890",
                "zoho_desk_ticket_id": "ZD-11111",
                "is_key_account": True,
                "is_seller_in_golden_list": True,
            }
        )

        # Create the message
        message = SlackMessageIncidentDeclaredAnnouncement(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # Find the SectionBlock with fields (should contain custom fields)
        # This is typically the 4th block (index 3)
        fields_block = None
        for block in blocks:
            if hasattr(block, "fields") and block.fields:
                fields_block = block
                break

        assert fields_block is not None, "Should have a block with fields"

        # Convert fields to strings for easier assertion (access .text attribute)
        fields_text = " ".join(field.text if hasattr(field, "text") else str(field) for field in fields_block.fields)

        # Verify custom fields are present
        assert "Zendesk Ticket" in fields_text
        assert "12345" in fields_text
        assert "Seller Contract" in fields_text
        assert "SELLER-67890" in fields_text
        assert "Zoho Desk Ticket" in fields_text
        assert "ZD-11111" in fields_text
        assert "Key Account" in fields_text
        assert "Golden List Seller" in fields_text

    def test_custom_fields_not_displayed_when_absent(self) -> None:
        """Test that custom fields are NOT displayed when not present."""
        # Create an incident WITHOUT custom fields
        incident = IncidentFactory.create(custom_fields={})

        # Create the message
        message = SlackMessageIncidentDeclaredAnnouncement(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # Find the SectionBlock with fields
        fields_block = None
        for block in blocks:
            if hasattr(block, "fields") and block.fields:
                fields_block = block
                break

        assert fields_block is not None, "Should have a block with fields"

        # Convert fields to strings (access .text attribute)
        fields_text = " ".join(field.text if hasattr(field, "text") else str(field) for field in fields_block.fields)

        # Verify custom fields are NOT present
        assert "Zendesk Ticket" not in fields_text
        assert "Seller Contract" not in fields_text
        assert "Zoho Desk Ticket" not in fields_text
        assert "Key Account" not in fields_text
        assert "Golden List Seller" not in fields_text

    def test_partial_custom_fields_displayed(self) -> None:
        """Test that only filled custom fields are displayed."""
        # Create an incident with only some custom fields
        incident = IncidentFactory.create(
            custom_fields={
                "zendesk_ticket_id": "12345",
                # seller_contract_id not set
                # zoho_desk_ticket_id not set
                "is_key_account": False,  # False should not display
                # is_seller_in_golden_list not set
            }
        )

        # Create the message
        message = SlackMessageIncidentDeclaredAnnouncement(incident=incident)

        # Get the blocks
        blocks = message.get_blocks()

        # Find the SectionBlock with fields
        fields_block = None
        for block in blocks:
            if hasattr(block, "fields") and block.fields:
                fields_block = block
                break

        assert fields_block is not None, "Should have a block with fields"

        # Convert fields to strings (access .text attribute)
        fields_text = " ".join(field.text if hasattr(field, "text") else str(field) for field in fields_block.fields)

        # Verify only zendesk_ticket_id is present
        assert "Zendesk Ticket" in fields_text
        assert "12345" in fields_text

        # Verify others are NOT present
        assert "Seller Contract" not in fields_text
        assert "Zoho Desk Ticket" not in fields_text
        assert "Key Account" not in fields_text
        assert "Golden List Seller" not in fields_text
