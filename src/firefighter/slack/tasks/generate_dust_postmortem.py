"""Ask the Dust agent to fill in an incident's post-mortem.

The first implementation posted an instruction addressed to the Dust bot in the
incident channel and relied on the agent reading it. It did not work reliably,
so Dust exposes a webhook for exactly this: the payload names the channel to
work from and the Jira post-mortem to fill, and is signed with a shared secret.

The bot is still invited to the channel first: the agent reports back there, and
a bot that is not a member cannot post.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
from celery import shared_task
from django.conf import settings
from slack_sdk.errors import SlackApiError

from firefighter.firefighter.http_client import HttpClient
from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "signature"
SIGNATURE_PREFIX = "sha256="


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


def build_dust_message(incident: Incident, jira_issue_key: str) -> str:
    """The instruction handed to the agent: which channel to read, which ticket to fill."""
    channel = incident.conversation
    return (
        f"Please fill in the post-mortem Jira ticket {jira_issue_key} for incident "
        f"#{incident.id} ({incident.title}). The incident was handled in the Slack "
        f"channel #{channel.name} ({channel.channel_id}): read through it and "
        "complete the post-mortem with the summary, timeline, root cause, impact "
        "and action items."
    )


def sign_payload(body: bytes, secret: str) -> str:
    """`sha256=<hex>` HMAC of the exact bytes sent, as the webhook expects."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def _call_dust_webhook(url: str, secret: str, message: str) -> None:
    """POST the signed payload.

    The body is serialized once and sent as raw bytes: signing a dict and
    letting the HTTP client re-serialize it would produce a signature over
    different bytes than the ones on the wire.
    """
    body = json.dumps({"message": message}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sign_payload(body, secret),
    }
    with HttpClient() as client:
        response = client.post(url, content=body, headers=headers)
    response.raise_for_status()


@shared_task(
    name="slack.generate_dust_postmortem",
    autoretry_for=(SlackApiError, httpx.HTTPError),
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
        logger.warning(
            "Incident %s has no Slack channel, skipping Dust trigger", incident_id
        )
        return

    jira_postmortem = getattr(incident, "jira_postmortem_for", None)
    if jira_postmortem is None:
        # The agent's whole job is to fill that ticket in; without one there is
        # nothing for it to write to.
        logger.warning(
            "Incident %s has no Jira post-mortem, skipping Dust trigger", incident_id
        )
        return

    webhook_url: str | None = settings.DUST_WEBHOOK_URL
    webhook_secret: str | None = settings.DUST_WEBHOOK_SECRET
    if not webhook_url or not webhook_secret:
        logger.warning(
            "Dust webhook is not configured (URL or secret missing), skipping Dust trigger"
        )
        return

    channel_id: str = incident.conversation.channel_id
    bot_name: str = settings.DUST_SLACK_BOT_NAME
    bot_user_id = _resolve_bot_user_id(client, bot_name)
    if bot_user_id:
        # Best effort: the agent answers in the channel, so it has to be a member.
        try:
            client.conversations_invite(channel=channel_id, users=[bot_user_id])
            logger.info("Invited Dust bot %s to channel %s", bot_user_id, channel_id)
        except SlackApiError as e:
            if e.response.get("error") != "already_in_channel":
                raise
            logger.info("Dust bot already in channel %s", channel_id)
    else:
        logger.warning(
            "Dust bot '%s' not found in workspace; calling the webhook anyway", bot_name
        )

    _call_dust_webhook(
        webhook_url,
        webhook_secret,
        build_dust_message(incident, jira_postmortem.jira_issue_key),
    )
    logger.info(
        "Called the Dust webhook for incident %s (post-mortem %s)",
        incident_id,
        jira_postmortem.jira_issue_key,
    )
