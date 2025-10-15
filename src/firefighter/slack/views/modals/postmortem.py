from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.apps import apps
from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if apps.is_installed("firefighter.confluence"):
    from firefighter.confluence.models import PostMortem

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident


logger = logging.getLogger(__name__)


class PostMortemModal(
    IncidentSelectableModalMixin,
    SlackModal,
):
    open_action: str = "open_modal_create_postmortem"
    push_action: str = "push_modal_create_postmortem"
    callback_id: str = "incident_create_postmortem"

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks: list[Block] = []
        if hasattr(incident, "postmortem_for"):
            blocks.extend([
                SectionBlock(
                    text=f"Postmortem for incident #{incident.id} has already been created."
                ),
                SectionBlock(
                    text=f"See the postmortem page <{incident.postmortem_for.page_url}|on Confluence>."
                ),
            ])
            submit = None
        else:
            blocks.extend([
                SectionBlock(
                    text=f"Postmortem does not yet exist for incident #{incident.id}."
                ),
                SectionBlock(
                    text="Click on the button to create the postmortem on Confluence."
                ),
            ])
            submit = "Create postmortem"[:24]

        return View(
            type="modal",
            title="Postmortem"[:24],
            submit=submit,
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    @staticmethod
    def handle_modal_fn(ack: Ack, body: dict[str, Any], incident: Incident) -> None:  # type: ignore[override]
        if not apps.is_installed("firefighter.confluence"):
            ack(text="Confluence is not enabled!")
            return
        if hasattr(incident, "postmortem_for"):
            ack(text="Post-mortem has already been created.")
            return

        # Check if this modal was pushed on top of another modal
        # If yes, clear the entire stack to avoid leaving stale modals visible
        is_pushed = body.get("view", {}).get("previous_view_id") is not None
        if is_pushed:
            ack(response_action="clear")
        else:
            ack()

        PostMortem.objects.create_postmortem_for_incident(incident)


modal_postmortem = PostMortemModal()
