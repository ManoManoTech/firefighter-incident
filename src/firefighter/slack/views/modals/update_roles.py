from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.models.views import View

from firefighter.incidents.forms.update_roles import IncidentUpdateRolesForm
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.views.modals.base_modal.base import ModalForm
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, User
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


class IncidentUpdateRolesFormSlack(IncidentUpdateRolesForm):
    slack_fields: SlackFormAttributesDict = {}


class UpdateRolesModal(
    IncidentSelectableModalMixin, ModalForm[IncidentUpdateRolesFormSlack]
):
    open_action: str = "open_modal_incident_update_roles"
    update_action: str = "update_modal_incident_update_roles"
    push_action: str = "push_modal_incident_update_roles"
    callback_id: str = "incident_update_roles"
    form_class = IncidentUpdateRolesFormSlack

    def build_modal_fn(self, incident: Incident, user: User, **kwargs: Any) -> View:
        blocks = self.get_form_class()(
            incident=incident,
            user=user,
        ).slack_blocks()
        blocks.append(slack_block_separator())
        blocks.append(slack_block_footer())
        return View(
            type="modal",
            title=f"Update roles for #{incident.id}"[:24],
            submit="Update roles"[:24],
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    def handle_modal_fn(  # type: ignore
        self, ack: Ack, body: dict[str, Any], incident: Incident, user: User
    ):
        slack_form = self.handle_form_errors(
            ack,
            body,
            forms_kwargs={
                "incident": incident,
                "user": user,
            },
        )
        if slack_form is None:
            return
        form: IncidentUpdateRolesFormSlack = slack_form.form

        if len(form.cleaned_data) == 0:
            # XXX We should have a prompt for empty forms
            return
        form.save()


modal_update_roles = UpdateRolesModal()
