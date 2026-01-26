from __future__ import annotations

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import IncidentUpdate
from firefighter.jira_app.models import JiraPostMortem
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import SlackMessageIncidentStatusUpdated


@pytest.mark.django_db
class TestSlackMessagePostMortemReminder:
    """Test post mortem reminder functionality in status update messages."""

    def test_shows_postmortem_reminder_when_returning_to_mitigated_with_existing_postmortem(self):
        """Test that post mortem reminder is shown when incident returns to MITIGATED and has existing post mortem."""
        # Create an incident in MITIGATED status
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create an existing Jira post mortem
        jira_postmortem = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
        )

        # Create an IncidentUpdate
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            created_by=user,
            message="Incident is back to mitigated after investigation"
        )

        # Create the message
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=True,
            status_changed=True,
        )

        # Get the blocks
        blocks = message.get_blocks()

        # Convert blocks to text for easier searching
        blocks_text = str(blocks)

        # Should contain the post mortem reminder
        assert "Reminder" in blocks_text
        assert "already has an existing post mortem" in blocks_text
        assert jira_postmortem.jira_issue_key in blocks_text
        assert jira_postmortem.issue_url in blocks_text
        assert "Open documentation" in blocks_text
        assert "https://manomano.atlassian.net/wiki/spaces/TC/pages/5639635000" in blocks_text

    def test_no_postmortem_reminder_when_mitigated_without_existing_postmortem(self):
        """Test that no post mortem reminder is shown when incident is MITIGATED but has no existing post mortem."""
        # Create an incident in MITIGATED status (no post mortem)
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create an IncidentUpdate
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            created_by=user
        )

        # Create the message
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=True,
            status_changed=True,
        )

        # Get the blocks
        blocks = message.get_blocks()

        # Convert blocks to text for easier searching
        blocks_text = str(blocks)

        # Should NOT contain the post mortem reminder
        assert "Reminder" not in blocks_text
        assert "already has an existing post mortem" not in blocks_text

    def test_no_postmortem_reminder_when_not_mitigated_with_existing_postmortem(self):
        """Test that no post mortem reminder is shown when incident has post mortem but is not in MITIGATED status."""
        # Create an incident in INVESTIGATING status
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Create an IncidentChannel
        IncidentChannelFactory.create(incident=incident)

        # Create an existing Jira post mortem
        JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INCIDENT-123",
            jira_issue_id="10001",
        )

        # Create an IncidentUpdate
        user = UserFactory.create()
        incident_update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            created_by=user
        )

        # Create the message
        message = SlackMessageIncidentStatusUpdated(
            incident=incident,
            incident_update=incident_update,
            in_channel=True,
            status_changed=True,
        )

        # Get the blocks
        blocks = message.get_blocks()

        # Convert blocks to text for easier searching
        blocks_text = str(blocks)

        # Should NOT contain the post mortem reminder
        assert "Reminder" not in blocks_text
        assert "already has an existing post mortem" not in blocks_text
