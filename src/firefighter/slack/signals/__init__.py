from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

import django.dispatch

from firefighter.slack.signals.incident_closed import incident_closed_slack

if TYPE_CHECKING:
    from firefighter.slack.signals import incident_updated

incident_channel_done = django.dispatch.Signal()

__all__ = ["incident_channel_done", "incident_closed_slack", "incident_updated"]


def __getattr__(name: str) -> Any:
    """Lazy import to avoid circular dependencies."""
    if name == "incident_updated":
        return importlib.import_module(".incident_updated", package="firefighter.slack.signals")
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
