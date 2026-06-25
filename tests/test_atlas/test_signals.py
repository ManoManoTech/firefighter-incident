"""Tests for Atlas signal handler."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from firefighter.atlas.signals import (
    _MAX_PRIORITY_VALUE,
    trigger_atlas_incident_analysis,
)


def _make_incident(priority_value: int, env_value: str = "PRD") -> Mock:
    incident = Mock()
    incident.id = 1
    incident.priority.value = priority_value
    incident.priority.name = f"P{priority_value}"
    incident.environment.value = env_value
    return incident


def _make_channel(channel_id: str = "C123456") -> Mock:
    channel = Mock()
    channel.channel_id = channel_id
    return channel


@pytest.mark.parametrize("priority_value", range(1, _MAX_PRIORITY_VALUE + 1))
@patch("firefighter.atlas.tasks.request_analysis.request_incident_analysis")
def test_enqueues_task_for_high_priority_prd(mock_task: Mock, priority_value: int) -> None:
    incident = _make_incident(priority_value)
    channel = _make_channel()

    trigger_atlas_incident_analysis(sender=None, incident=incident, channel=channel)

    mock_task.delay.assert_called_once_with(incident.id, channel.channel_id)


@pytest.mark.parametrize("priority_value", [4, 5])
@patch("firefighter.atlas.tasks.request_analysis.request_incident_analysis")
def test_skips_low_priority(mock_task: Mock, priority_value: int) -> None:
    incident = _make_incident(priority_value)
    channel = _make_channel()

    trigger_atlas_incident_analysis(sender=None, incident=incident, channel=channel)

    mock_task.delay.assert_not_called()


@pytest.mark.parametrize("env_value", ["STG", "INT", "DEV", "TST"])
@patch("firefighter.atlas.tasks.request_analysis.request_incident_analysis")
def test_enqueues_task_for_any_environment(mock_task: Mock, env_value: str) -> None:
    """All environments trigger Atlas analysis — only priority is gated."""
    incident = _make_incident(priority_value=1, env_value=env_value)
    channel = _make_channel()

    trigger_atlas_incident_analysis(sender=None, incident=incident, channel=channel)

    mock_task.delay.assert_called_once_with(incident.id, channel.channel_id)


@patch("firefighter.atlas.tasks.request_analysis.request_incident_analysis")
def test_enqueue_failure_does_not_propagate(mock_task: Mock) -> None:
    """Broker errors on .delay() must not break the signal chain."""
    mock_task.delay.side_effect = ConnectionError("broker unreachable")
    incident = _make_incident(priority_value=1)
    channel = _make_channel()

    # Should not raise
    trigger_atlas_incident_analysis(sender=None, incident=incident, channel=channel)
