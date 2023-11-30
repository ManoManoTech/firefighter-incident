from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from firefighter.slack.models.message import Message
from firefighter.slack.slack_app import SlackApp

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event(
    {"type": "message", "subtype": "message_deleted"},
)
def handle_message_deleted(event: dict[str, Any]) -> None:
    channel_id = event.get("channel")
    ts = event.get("deleted_ts")
    if not channel_id or not ts:
        raise ValueError("Missing channel_id or ts")
    ts_dt = datetime.fromtimestamp(float(ts), tz=UTC)

    # Delete from DB if exists
    Message.objects.filter(
        conversation__channel_id=channel_id,
        ts=ts_dt,
    ).delete()
