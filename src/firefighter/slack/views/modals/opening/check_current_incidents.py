from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from django.utils.translation import ngettext as _
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import (
    Block,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.incidents.models.incident import Incident
from firefighter.slack.views.modals.base_modal.base import SlackModal


class CheckCurrentIncidentsModal(
    SlackModal,
):
    handle_modal_fn = None
    open_action = "open_check_current_incidents"
    push_action: str = "push_check_current_incidents"
    callback_id = "check_current_incidents"

    @staticmethod
    def build_modal_fn(body: dict[str, Any], **kwargs: Any) -> View:
        # ruff: noqa: PLC0415
        from firefighter.slack.views.events.home import _home_incident_element

        # Close or back button?
        view: dict[str, Any] = body.get("view", {})
        close_text = (
            "Back"
            if view.get("root_view_id") or not view.get("clear_on_close")
            else "Close"
        )

        incidents = list(
            Incident.objects.filter(

                created_at__gte=datetime.now(UTC) - timedelta(hours=1)
            )
            .order_by("-created_at")
            .select_related(
                "priority",
                "incident_category",
                "environment",
                "incident_category__group",
                "conversation",
            )[:30]
        )
        if len(incidents) == 0:
            blocks: list[Block] = [
                SectionBlock(
                    text=MarkdownTextObject(text="No incidents in the past hour.")
                )
            ]
        else:
            blocks = [
                SectionBlock(
                    text=MarkdownTextObject(
                        text=_(
                            "Below is the incident that has been created in the past hour.",
                            "Below are the incidents that have been created in the past hour.",
                            len(incidents),
                        )
                    )
                )
            ]
        for incident in incidents:
            blocks.extend(_home_incident_element(incident, show_actions=False))

        return View(
            type="modal",
            title="Last critical incidents"[:24],
            blocks=blocks,
            close=close_text,
        )


modal_checker = CheckCurrentIncidentsModal()
