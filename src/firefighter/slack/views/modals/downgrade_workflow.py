from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.incidents.enums import IncidentStatus
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


logger = logging.getLogger(__name__)


class DowngradeWorkflowModal(
    IncidentSelectableModalMixin,
    SlackModal,
):
    open_action: str = "open_modal_downgrade_workflow"
    push_action: str = "push_modal_downgrade_workflow"
    update_action: str = "update_modal_downgrade_workflow"
    callback_id: str = "incident_downgrade_workflow"

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks: list[Block] = []
        if hasattr(incident, "jira_ticket") and incident.jira_ticket:
            jira_txt = f":jira_new: <{incident.jira_ticket.url}|*Jira ticket*>"
        else:
            jira_txt = "No Jira ticket!"
            # XXX Return error (weird state)
        if incident.status == IncidentStatus.CLOSED:
            blocks.extend((
                SectionBlock(text=f"Incident #{incident.id} is already closed."),
                SectionBlock(text=jira_txt),
            ))
            submit = None
        else:
            blocks.extend((
                SectionBlock(
                    text=f"By clicking this button you will close incident #{incident.id}."
                ),
                SectionBlock(
                    text=f"It will:\n- Archive the Slack channel #{incident.conversation.name}\n- Ignore the critical incident\n- Keep it as a normal incident, with its {jira_txt}."
                ),
            ))
            submit = "Mark as regular incident"[:24]

        return View(
            type="modal",
            title="Mark as regular incident"[:24],
            submit=submit,
            close="Cancel",
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    @staticmethod
    def handle_modal_fn(ack: Ack, user: User, incident: Incident) -> None:  # type: ignore[override]
        # XXX(dugab): error handling
        incident.ignore = True
        incident.save()
        jira_txt = (
            ": " + incident.jira_ticket.url
            if hasattr(incident, "jira_ticket") and incident.jira_ticket
            else "."
        )
        incident.create_incident_update(
            created_by=user,
            status=IncidentStatus.CLOSED,
            message=f"Incident channel closed - follow the incident on its Jira Ticket{jira_txt}",
        )
        ack()

    def get_select_title(self) -> str:
        return "Select a critical incident you want to convert to a Jira incident"


modal_dowgrade_workflow = DowngradeWorkflowModal()
