from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.models.views import View
    from slack_sdk.web.client import WebClient

logger = logging.getLogger(__name__)


@slack_client
def open_modal(
    view: View,
    trigger_id: str | None = None,
    body: dict[str, Any] | None = None,
    client: WebClient = DefaultWebClient,
) -> None:
    if trigger_id is None and body is None:
        raise ValueError("Please provide either a trigger_id or a body containing one!")

    if trigger_id is None and body is not None:
        trigger_id = body.get("trigger_id")

    if trigger_id is None:
        raise ValueError("No trigger_id found!")
    client.views_open(trigger_id=trigger_id, view=view)


@slack_client
def push_modal(
    view: View,
    trigger_id: str | None = None,
    body: dict[str, Any] | None = None,
    client: WebClient = DefaultWebClient,
) -> None:
    if trigger_id is None and body is None:
        raise ValueError("Please provide either a trigger_id or a body containing one!")

    if trigger_id is None and body is not None:
        trigger_id = body.get("trigger_id")
    if trigger_id is None:
        raise ValueError("No trigger_id found!")
    client.views_push(trigger_id=trigger_id, view=view)


@slack_client
def update_modal(
    view: View,
    trigger_id: str | None = None,
    body: dict[str, Any] | None = None,
    view_id: str | None = None,
    external_id: str | None = None,
    hash_value: str | None = None,
    client: WebClient = DefaultWebClient,
    **kwargs: Any,
) -> None:
    if body is None and trigger_id is None and (view_id is None or external_id is None):
        raise ValueError("We need a body or args here!")

    if hash_value is None:
        hash_value = get_in(body, "view.hash")

    if trigger_id is None and body is not None:
        trigger_id = body.get("trigger_id")

    if external_id is None:
        external_id = get_in(body, "view.external_id")

    if view_id is None:
        view_id = get_in(body, "container.view_id")
        if view_id is None:
            view_id = get_in(body, "view.id")

    client.views_update(
        trigger_id=trigger_id,
        view_id=view_id,
        external_id=external_id,
        hash=hash_value,
        view=view,
        **kwargs,
    )
