from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone
from slack_sdk.errors import SlackApiError, SlackRequestError
from slack_sdk.models.blocks.basic_components import MarkdownTextObject, Option
from slack_sdk.models.blocks.block_elements import ButtonElement, OverflowMenuElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
    Block,
    DividerBlock,
    HeaderBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.firefighter.utils import get_first_in, get_in
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.slack_app import DefaultWebClient, SlackApp
from firefighter.slack.slack_templating import (
    date_time,
    slack_block_footer,
    slack_block_help_commands,
    slack_block_help_description,
    slack_block_help_tip,
    slack_block_quote,
)
from firefighter.slack.views.modals.close import CloseModal
from firefighter.slack.views.modals.open import OpenModal
from firefighter.slack.views.modals.update import UpdateModal
from firefighter.slack.views.modals.update_status import modal_update_status

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack
    from slack_sdk.web.client import WebClient

APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME
SLACK_APP_EMOJI: str = settings.SLACK_APP_EMOJI

app = SlackApp()

logger = logging.getLogger(__name__)


@app.event("app_home_opened")
def update_home_tab(
    event: dict[str, Any], client: WebClient = DefaultWebClient
) -> None:
    logger.debug(event)
    # Show only the latest 30 incidents, as Slack does not allow more than 100 elements
    shown_incidents = list(
        Incident.objects.filter(_status__lt=IncidentStatus.CLOSED.value)
        .order_by("-id")
        .select_related(
            "priority", "incident_category", "environment", "incident_category__group", "conversation"
        )[:30]
    )
    blocks: list[Block] = [
        HeaderBlock(text=f"{APP_DISPLAY_NAME} - Incident Management"),
        slack_block_help_description(),
        slack_block_help_commands(),
        slack_block_help_tip(),
        DividerBlock(),
        ActionsBlock(
            block_id="home_actions",
            elements=[
                ButtonElement(
                    text="Open incident",
                    value="open_incident_home_button",
                    style="primary",
                    action_id=OpenModal.open_action,
                ),
                ButtonElement(
                    text="Update critical incident",
                    value="update_incident_home_button",
                    style="primary",
                    action_id=UpdateModal.open_action,
                ),
                ButtonElement(
                    text="Close critical incident",
                    value="close_incident_home_button",
                    style="primary",
                    action_id=CloseModal.open_action,
                ),
            ],
        ),
        HeaderBlock(
            text=f"{len(shown_incidents)} critical incidents active at {datetime.now(tz=timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M:%S')}"
        ),
    ]

    if len(shown_incidents) == 0:
        blocks.extend((
            DividerBlock(),
            SectionBlock(text="No active incidents! Enjoy :tada:"),
        ))
    else:
        for incident in shown_incidents:
            blocks.extend(_home_incident_element(incident))
    blocks.extend((DividerBlock(), slack_block_footer()))
    view = View(type="home", blocks=blocks)

    try:
        client.views_publish(user_id=event["user"], view=view)
    except (SlackApiError, SlackRequestError):
        logger.exception("Error publishing home tab!")


@app.action("app_home_incident_action")
def handle_some_action(ack: Ack, body: dict[str, Any]) -> None:
    logger.debug(body)

    action = get_first_in(
        body.get("actions", ""),
        key=("selected_option", "value"),
        matches=("update_status", "open_link"),
    )

    action_selected = get_in(action, "selected_option.value")
    if action_selected == "update_status":
        modal_update_status.open_modal_aio(ack, body)

    elif action_selected == "open_link":
        ack()

    else:
        logger.warning(f"Unknown action ! {action_selected}")


def _home_incident_element(
    incident: Incident, *, show_actions: bool = True
) -> list[Block]:
    blocks: list[Block] = [
        DividerBlock(),
        SectionBlock(
            block_id=f"app_home_incident_element_{incident.id}",
            text=f"*#{incident.slack_channel_name if incident.slack_channel_name is not None else incident.id}* - *{incident.title}* - {SLACK_APP_EMOJI} <{incident.status_page_url + '?utm_medium=FireFighter+Slack&utm_source=Slack+Home&utm_campaign=Slack+Home+Link'}| Status Page>",
            fields=[
                MarkdownTextObject(
                    text=f":information_source: *Status:* {incident.status.label}"
                ),
                MarkdownTextObject(
                    text=f":rotating_light: *Priority:* {incident.priority.emoji} {incident.priority.name}"
                ),
                MarkdownTextObject(
                    text=f":package: *Incident category:* {incident.incident_category.group.name} - {incident.incident_category.name}"
                ),
                MarkdownTextObject(
                    text=f":speaking_head_in_silhouette: *Last update:* {date_time(incident.updated_at)}"
                ),
            ],
            accessory=(
                OverflowMenuElement(
                    action_id="app_home_incident_action",
                    options=[
                        Option(text="Update status", value="update_status"),
                        Option(
                            text="See status page",
                            url=incident.status_page_url
                            + "?utm_medium=FireFighter+Slack&utm_source=Slack+Home&utm_campaign=Slack+Home+Button",
                            value="open_link",
                        ),
                    ],
                )
                if show_actions
                else None
            ),
        ),
        slack_block_quote(incident.description, length=1500),
    ]

    return blocks
