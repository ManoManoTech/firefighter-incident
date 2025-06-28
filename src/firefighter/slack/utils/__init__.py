from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Final

from django.utils.timezone import localtime
from slack_sdk.errors import SlackApiError

from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slack_sdk.models.blocks import Block
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)

NON_ALPHANUMERIC_CHARACTERS: Final[re.Pattern[str]] = re.compile(r"[^\da-zA-Z]+")


@slack_client
def respond(
    body: dict[str, Any],
    text: str = "",
    blocks: str | Sequence[dict[str, Any] | Block] | None = None,
    client: WebClient = DefaultWebClient,
) -> None:
    """Respond to the user, depending on where the message was coming from."""
    user_id: str | None = body.get("user_id", body.get("user", {}).get("id"))
    channel_id: str | None = body.get("channel_id", body.get("channel", {}).get("id"))

    if not user_id and not channel_id:
        raise ValueError(
            "Cannot find user_id (or user.id) or channel_id (or channel.id) in the body. At least one is required."
        )

    # From Direct Message => Always respond on the conv between the user and the bot.
    if (body.get("channel_name") == "directmessage" or not channel_id) and user_id:
        # We should always be able to respond in this conversation...
        client.chat_postMessage(channel=user_id, text=text, blocks=blocks)
        return
    if not user_id:
        raise ValueError("Cannot find user_id (or user.id) in the body.")

    # From channel => post as ephemeral in the channel
    try:
        _send_ephemeral(text, blocks, client, user_id, channel_id)

    except (SlackApiError, ValueError):
        logger.warning(
            "Failed to send ephemeral chat message to user! Body: %s",
            body,
            exc_info=True,
        )
        # Fallback to DM
        if body.get("type") != "view_submission":
            client.chat_postMessage(
                channel=user_id,
                text=":warning: The bot could not respond in the channel you invoked it. Please add it to this channel or conversation if you want to interact with the bot there. If you believe this is a bug, please tell @pulse.",
            )
        client.chat_postMessage(channel=user_id, text=text, blocks=blocks)


def _send_ephemeral(
    text: str,
    blocks: str | Sequence[dict[str, Any] | Block] | None,
    client: WebClient,
    user_id: str,
    channel_id: str | None,
) -> None:
    if not channel_id:
        raise ValueError("Cannot find channel_id (or channel.id) in the body.")
    client.chat_postEphemeral(
        user=user_id, channel=channel_id, text=text, blocks=blocks
    )


def get_slack_user_id_from_body(body: dict[str, Any]) -> str | None:
    """Get the slack user id from the body of a Slack request, in `user_id` or `user.id`."""
    return body.get("user_id", body.get("user", {}).get("id"))


def channel_name_from_incident(incident: Incident) -> str:
    """Lowercase, truncated at 80 chars, this is obviously the channel #name.

    The environment(s) are included in the channel name to clearly indicate scope.
    When multiple environments are affected, all are displayed sorted by priority.
    If the name exceeds 80 characters, environments are abbreviated progressively.
    """
    if (
        not hasattr(incident, "created_at")
        or not hasattr(incident, "id")
        or not incident.created_at
        or not incident.id
    ):
        raise RuntimeError(
            "Incident must be saved before slack_channel_name can be computed"
        )
    date_formatted = localtime(incident.created_at).strftime("%Y%m%d")

    # Get all environments from custom_fields, fallback to single environment field
    environments_list = incident.custom_fields.get("environments", [])
    if not environments_list and incident.environment is not None:
        environments_list = [incident.environment.value]

    # Sort environments by priority (assuming order: PRD < STG < INT < support)
    # This puts the most important environment first
    env_priority = {"PRD": 0, "STG": 1, "INT": 2, "support": 3}
    if environments_list:
        sorted_envs = sorted(environments_list, key=lambda e: env_priority.get(e, 99))
        env_str = "-".join(sorted_envs)
    else:
        env_str = ""

    # Build channel name with all environments
    if env_str:
        topic = f"{date_formatted}-{str(incident.id)[:8]}-{env_str}-{incident.incident_category.name}"
    else:
        topic = f"{date_formatted}-{str(incident.id)[:8]}-{incident.incident_category.name}"

    # Strip non-alphanumeric characters
    topic = topic.replace(" ", "-")
    topic = NON_ALPHANUMERIC_CHARACTERS.sub("-", topic)
    topic_clean = topic.lower()

    # Slack channel name limit is 80 characters
    # If too long, try to abbreviate environments progressively
    if len(topic_clean) > 80:
        # Try with abbreviated environments (first 3 chars)
        if environments_list:
            abbrev_envs = "-".join([e[:3] for e in sorted_envs])
            topic = f"{date_formatted}-{str(incident.id)[:8]}-{abbrev_envs}-{incident.incident_category.name}"
            topic = topic.replace(" ", "-")
            topic = NON_ALPHANUMERIC_CHARACTERS.sub("-", topic)
            topic_clean = topic.lower()

        # If still too long, truncate at 80 chars
        if len(topic_clean) > 80:
            topic_clean = topic_clean[:80]

    return topic_clean
