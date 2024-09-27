from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import ActionsBlock
from slack_sdk.models.views import View

from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)
from firefighter.slack.views.modals.edit import EditMetaModal
from firefighter.slack.views.modals.update_roles import UpdateRolesModal
from firefighter.slack.views.modals.update_status import UpdateStatusModal

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)


class UpdateModal(
    IncidentSelectableModalMixin,
    SlackModal,
):
    handle_modal_fn = None
    open_action: str = "update_incident"
    callback_id: str = "incident_update"

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        return View(
            type="modal",
            title=f"Update incident #{incident.id}"[:24],
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=[
                ActionsBlock(
                    block_id="choose_update_type",
                    elements=[
                        ButtonElement(
                            text="Update status",
                            action_id=UpdateStatusModal.push_action,
                        ),
                        ButtonElement(
                            text="Update roles",
                            action_id=UpdateRolesModal.push_action,
                        ),
                        ButtonElement(
                            text="Edit meta",
                            action_id=EditMetaModal.push_action,
                        ),
                    ],
                )
            ],
        )

    def get_select_modal_title(self) -> str:
        return "Update incident"

    def get_select_title(self) -> str:
        return "Select a critical incident to update"


modal_update = UpdateModal()
