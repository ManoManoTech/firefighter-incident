from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task
from slack_sdk.errors import SlackClientError

from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient

logger = logging.getLogger(__name__)


@shared_task(
    name="slack.send_message",
    autoretry_for=(SlackClientError,),
    retry_kwargs={"max_retries": 2},
    default_retry_delay=30,
)
@slack_client
def send_message(  # pylint: disable=keyword-arg-before-vararg
    client: WebClient = DefaultWebClient, *args: Any, **kwargs: Any
) -> dict[str, Any] | bytes:
    """Sends a message to a channel. All arguments are passed to the Slack API."""
    return client.chat_postMessage(*args, **kwargs).data
