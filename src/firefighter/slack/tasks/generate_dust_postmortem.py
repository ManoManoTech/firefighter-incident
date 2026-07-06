from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.conf import settings
from slack_sdk.errors import SlackApiError

from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)


def _resolve_bot_user_id(client: WebClient, bot_name: str) -> str | None:
    """Find the Slack user ID of a bot app by its display name."""
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.users_list(**kwargs)
        members: list[dict[str, Any]] = response.get("members") or []
        for member in members:
            if member.get("is_bot") and member.get("name") == bot_name:
                return member["id"]
        response_metadata: dict[str, Any] = response.get("response_metadata") or {}
        cursor = response_metadata.get("next_cursor")
        if not cursor:
            break
    return None


def _build_dust_message(bot_user_id: str, incident: Incident) -> str:
    """Build the English instruction posted to the Dust agent in the channel."""
    jira_pm = getattr(incident, "jira_postmortem_for", None)
    ticket_ref = (
        f"the post-mortem Jira ticket <{jira_pm.issue_url}|{jira_pm.jira_issue_key}>"
        if jira_pm is not None
        else "the post-mortem for this incident"
    )
    return (
        f"<@{bot_user_id}> ~IncidentManagementPostMortem "
        f"Please update {ticket_ref} for this incident. "
        "Read through this incident channel and fill in the post-mortem: "
        "summary, timeline, root cause, impact, and action items."
    )


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

    incident = Incident.objects.select_related(
        "conversation", "jira_postmortem_for"
    ).get(id=incident_id)
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
        text=_build_dust_message(bot_user_id, incident),
    )
    logger.info("Sent Dust post-mortem generation request for incident %s", incident_id)
