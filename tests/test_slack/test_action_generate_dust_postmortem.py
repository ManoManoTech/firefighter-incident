from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_action_acks_and_dispatches_task() -> None:
    """Handler acks immediately then dispatches the Celery task with the incident_id."""
    from firefighter.slack.views.events.actions_and_shortcuts import (
        generate_dust_postmortem_action,
    )

    ack = MagicMock()
    body = {"actions": [{"value": "42"}]}

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem.generate_dust_postmortem.delay"
    ) as mock_delay:
        generate_dust_postmortem_action(ack=ack, body=body)

    ack.assert_called_once()
    mock_delay.assert_called_once_with(42)
