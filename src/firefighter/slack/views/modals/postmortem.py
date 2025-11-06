from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

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
                SectionBlock(text=f"Post-mortem(s) for incident #{incident.id}:")
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
        else:
            blocks.append(
                SectionBlock(
                    text=f"Post-mortem for incident #{incident.id} will be automatically created when the incident reaches MITIGATED status."
                )
            )

        return View(
            type="modal",
            title="Postmortem"[:24],
            submit=None,
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    @staticmethod
    def handle_modal_fn(ack: Ack, **_kwargs: Any) -> None:
        # This modal is now read-only (no submit button)
        # Post-mortems are created automatically when incident reaches MITIGATED status
        ack()


modal_postmortem = PostMortemModal()
