from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from firefighter.firefighter.utils import get_in
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.modals import selectable_modals
from firefighter.slack.views.modals.base_modal.modal_utils import update_modal

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.slack.views.modals.base_modal.base import SlackModal

app = SlackApp()

logger = logging.getLogger(__name__)


selectable_list: list[tuple[str, SlackModal]] = list(
    filter(
        lambda x: x[0] is not None,
        [
            (x.callback_id, x())
            for x in selectable_modals
            if isinstance(x.callback_id, str)
        ],
    )
)
selectable: dict[str, SlackModal] = dict(selectable_list)


@app.action("incident_update_select_incident")
def update_update_modal(ack: Ack, body: dict[str, Any]) -> None:
    """Reacts to the selection of an incident, in the select modal."""
    ack()
    logger.info(body)

    callback_id = get_in(body, "view.callback_id")
    if callback_id in selectable:
        view = selectable[callback_id].build_modal_with_context(
            body, callback_id=callback_id
        )
        update_modal(body=body, view=view)


@app.action("open_link")
def open_link(ack: Ack) -> None:
    """Does nothing. ack() is mandatory, even on buttons that open a URL."""
    ack()
