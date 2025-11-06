from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings
from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if apps.is_installed("firefighter.confluence"):
    from firefighter.confluence.models import PostMortem

if apps.is_installed("firefighter.jira_app"):
    pass

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

        # Check existing post-mortems
        has_confluence = hasattr(incident, "postmortem_for")
        has_jira = hasattr(incident, "jira_postmortem_for")

        if has_confluence or has_jira:
            blocks.append(
                SectionBlock(
                    text=f"Post-mortem(s) for incident #{incident.id} already exist:"
                )
            )

            if has_confluence:
                blocks.append(
                    SectionBlock(
                        text=f"• Confluence: <{incident.postmortem_for.page_url}|View page>"
                    )
                )

            if has_jira:
                blocks.append(
                    SectionBlock(
                        text=f"• Jira: <{incident.jira_postmortem_for.issue_url}|{incident.jira_postmortem_for.jira_issue_key}>"
                    )
                )

            submit = None
        else:
            # Show creation options
            enabled_backends = []
            enable_confluence = getattr(settings, "ENABLE_CONFLUENCE", False)
            enable_jira_postmortem = getattr(
                settings, "ENABLE_JIRA_POSTMORTEM", False
            )

            if enable_confluence:
                enabled_backends.append("Confluence")
            if enable_jira_postmortem:
                enabled_backends.append("Jira")

            if not enabled_backends:
                blocks.append(
                    SectionBlock(
                        text="❌ Post-mortem creation is currently disabled."
                    )
                )
                submit = None
            else:
                backends_text = " and ".join(enabled_backends)
                blocks.extend([
                    SectionBlock(
                        text=f"Post-mortem does not yet exist for incident #{incident.id}."
                    ),
                    SectionBlock(
                        text=f"Click the button to create post-mortem on {backends_text}."
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
        enable_confluence = getattr(settings, "ENABLE_CONFLUENCE", False)
        enable_jira_postmortem = getattr(settings, "ENABLE_JIRA_POSTMORTEM", False)

        # Check if any backend is enabled
        if not enable_confluence and not enable_jira_postmortem:
            ack(text="Post-mortem creation is disabled!")
            return

        # Check if post-mortem already exists
        has_confluence = hasattr(incident, "postmortem_for")
        has_jira = hasattr(incident, "jira_postmortem_for")

        if has_confluence and has_jira:
            ack(text="Post-mortem has already been created on both backends.")
            return
        if has_confluence and not enable_jira_postmortem:
            ack(text="Confluence post-mortem already exists.")
            return
        if has_jira and not enable_confluence:
            ack(text="Jira post-mortem already exists.")
            return

        # Check if this modal was pushed on top of another modal
        # If yes, clear the entire stack to avoid leaving stale modals visible
        is_pushed = body.get("view", {}).get("previous_view_id") is not None
        if is_pushed:
            ack(response_action="clear")
        else:
            ack()

        # Create post-mortem(s) based on enabled backends
        if apps.is_installed("firefighter.confluence"):
            PostMortem.objects.create_postmortem_for_incident(incident)


modal_postmortem = PostMortemModal()
