from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime
from slack_sdk.models.blocks.basic_components import TextObject
from slack_sdk.models.blocks.blocks import (
    Block,
    ContextBlock,
    HeaderBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.incidents.models.incident import Incident, IncidentUpdate
from firefighter.slack.slack_templating import (
    date_time,
    slack_block_quote,
    user_slack_handle_or_name,
)
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

logger = logging.getLogger(__name__)
BASE_URL = settings.BASE_URL


class StatusModal(
    IncidentSelectableModalMixin,
    SlackModal,
):
    handle_modal_fn = None
    open_action = "incident_status"
    open_shortcut = "incident_status"
    callback_id = "incident_status"

    @staticmethod
    def get_latest_update(incident: Incident, **kwargs: Any) -> IncidentUpdate | None:
        try:
            return (
                IncidentUpdate.objects.exclude(message__isnull=True, message__exact="")
                .filter(incident=incident)
                .latest("event_ts")
            )
        except IncidentUpdate.DoesNotExist:
            return None

    @staticmethod
    def build_modal_fn(incident: Incident, **kwargs: Any) -> View:
        last_update = StatusModal.get_latest_update(incident)
        if last_update is None:
            err_msg = f"No update found for incident #{incident.id}"
            raise ValueError(err_msg)

        incident_duration = naturaltime(incident.created_at).replace(" ago", "")

        blocks: list[Block] = [
            HeaderBlock(text=":memo:  Key details"),
            SectionBlock(
                text=f""":alarm_clock: *Opened*: {date_time(incident.created_at)}
:pager: *Status*: {incident.status.label}
:rotating_light: *Priority*: {incident.priority.name}
:world_map: *Environment*: {incident.environment.value}
:stopwatch: *Duration*: {incident_duration}
:globe_with_meridians: *Status page*: <{incident.status_page_url + "?utm_medium=FireFighter+Slack&utm_source=Slack+Modal&utm_campaign=Status+Modal+Link"}|Link>"""
            ),
        ]
        incident_roles_text: list[str] = [
            f"{incident_role.role_type.emoji} *{incident_role.role_type.name}*: {user_slack_handle_or_name(incident_role.user)}"
            for incident_role in incident.roles_set.all()
        ]
        incident_roles_text.append(
            f":speaking_head_in_silhouette: *Reporter*: {user_slack_handle_or_name(incident.created_by)}"
        )
        blocks.extend((
            HeaderBlock(text=":busts_in_silhouette:  Key participants"),
            SectionBlock(text="\n".join(incident_roles_text)),
        ))
        if last_update.message:
            last_update_time = naturaltime(last_update.created_at)

            blocks.extend((
                HeaderBlock(text=f":newspaper:  Last update ({last_update_time})"),
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f"Posted at {date_time(last_update.created_at)} by {user_slack_handle_or_name(last_update.created_by)} ",
                        )
                    ]
                ),
                slack_block_quote(last_update.message),
            ))

        return View(
            type="modal",
            title=f"Incident #{incident.id} status"[:24],
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    def get_select_modal_title(self) -> str:
        return "Get incident status"

    def get_select_title(self) -> str:
        return "Select a critical incident to see its status"


modal_status = StatusModal()
