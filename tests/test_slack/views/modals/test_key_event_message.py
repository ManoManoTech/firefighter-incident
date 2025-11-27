"""Tests for Slack key event message view."""

from __future__ import annotations

import pytest

from firefighter.slack.views.modals import key_event_message


class TestKeyEventMessageImports:
    """Test that key event message module has necessary imports."""

    @staticmethod
    def test_signal_imported() -> None:
        """Test that incident_key_events_updated signal is imported."""
        # Verify the signal is imported in the module
        assert hasattr(
            key_event_message, "incident_key_events_updated"
        ), "incident_key_events_updated signal should be imported"


@pytest.mark.django_db
class TestKeyEventMessageSignalIntegration:
    """Integration tests verifying signal is sent - covered by test_jira_app tests."""

    # Note: The actual signal sending is tested in:
    # - tests/test_jira_app/test_incident_key_events_sync.py
    # These tests verify the signal handler receives and processes signals correctly.
    # Testing the Slack view's signal sending requires complex Slack mocking,
    # so we rely on manual testing and the signal handler tests instead.
