from __future__ import annotations

import logging

from slack_sdk.models.blocks.basic_components import Option, TextObject
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
    Block,
    ContextBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixinBase,
)

logger = logging.getLogger(__name__)


class SelectModal(SlackModal):
    handle_modal_fn = None

    callback_id = "select_incident"

    def build_modal_fn(
        self,
        incident: Incident | None = None,
        callback_id: str | None = "update",
        select_class: IncidentSelectableModalMixinBase | None = None,
        *,
        missing_incident_error: bool = False,
    ) -> View:
        active_incidents = Incident.objects.filter(
            _status__lt=IncidentStatus.CLOSED
        ).order_by("-id")

        if select_class is None and isinstance(self, IncidentSelectableModalMixinBase):
            select_class = self
        elif select_class is None or not isinstance(
            select_class, IncidentSelectableModalMixinBase
        ):
            select_class = (
                self
                if isinstance(self, IncidentSelectableModalMixinBase)
                else IncidentSelectableModalMixinBase()
            )

        incident_options = [
            Option(
                value=str(inc.id),
                label=f"{inc.id}: {inc.title}"[:73],
            )
            for inc in active_incidents
        ]
        if len(incident_options) > 0:
            select_incident_blocks: list[Block] = [
                SectionBlock(text=select_class.get_select_title()),
                ActionsBlock(
                    block_id="incident_update_select_incident",
                    elements=[
                        StaticSelectElement(
                            action_id="incident_update_select_incident",
                            placeholder="Select an active incident",
                            options=incident_options,
                        ),
                    ],
                ),
            ]
        else:
            select_incident_blocks = [
                SectionBlock(
                    text=":x: This command requires an active incident. Please create one first."
                )
            ]
        if missing_incident_error:
            select_incident_blocks.append(
                ContextBlock(
                    elements=[TextObject(text=":x: Please select an incident!")]
                )
            )
        select_incident_blocks.extend((slack_block_separator(), slack_block_footer()))

        return View(
            type="modal",
            title=select_class.get_select_modal_title()[:24],
            callback_id=callback_id,
            private_metadata=str(incident.id) if incident else "",
            blocks=select_incident_blocks,
        )


modal_select = SelectModal()
