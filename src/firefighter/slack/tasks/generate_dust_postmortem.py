from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from slack_sdk.errors import SlackApiError

from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

logger = logging.getLogger(__name__)


def _resolve_bot_user_id(client: WebClient, bot_name: str) -> str | None:
    """Find the Slack user ID of a bot app by its display name."""
    cursor = None
    while True:
        kwargs: dict = {"limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.users_list(**kwargs)
        for member in response.get("members", []):
            if member.get("is_bot") and member.get("name") == bot_name:
                return member["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


@shared_task(
    name="slack.generate_dust_postmortem",
    autoretry_for=(SlackApiError,),
    retry_kwargs={"max_retries": 2},
    default_retry_delay=30,
)
@slack_client
def generate_dust_postmortem(
    incident_id: int,
    client: WebClient = DefaultWebClient,
) -> None:
    from firefighter.incidents.models.incident import Incident

    incident = Incident.objects.select_related("conversation").get(id=incident_id)
    if not hasattr(incident, "conversation"):
        logger.warning("Incident %s has no Slack channel, skipping Dust trigger", incident_id)
        return

    bot_name: str = settings.DUST_SLACK_BOT_NAME
    bot_user_id = _resolve_bot_user_id(client, bot_name)
    if not bot_user_id:
        logger.warning("Dust bot '%s' not found in workspace, skipping Dust trigger", bot_name)
        return

    channel_id: str = incident.conversation.channel_id

    try:
        client.conversations_invite(channel=channel_id, users=[bot_user_id])
        logger.info("Invited Dust bot %s to channel %s", bot_user_id, channel_id)
    except SlackApiError as e:
        if e.response.get("error") == "already_in_channel":
            logger.info("Dust bot already in channel %s", channel_id)
        else:
            raise

    client.chat_postMessage(
        channel=channel_id,
        text=f"<@{bot_user_id}> ~IncidentManagementPostMortem",
    )
    logger.info("Sent Dust post-mortem generation request for incident %s", incident_id)
