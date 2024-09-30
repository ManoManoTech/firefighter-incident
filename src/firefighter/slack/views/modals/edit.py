from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.models.views import View

from firefighter.incidents.forms.edit import EditMetaForm
from firefighter.slack.views.modals.base_modal.base import ModalForm

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


class EditMetaFormSlack(EditMetaForm):
    slack_fields: SlackFormAttributesDict = {
        "title": {
            "input": {
                "multiline": False,
                "placeholder": "Short, punchy description of what's happening.",
            },
            "block": {"hint": None},
        },
        "description": {
            "input": {
                "multiline": True,
                "placeholder": "Help people responding to the incident. This will be posted to #tech-incidents and on our internal status page.\nThis description can be edited later.",
            },
            "block": {"hint": None},
        },
        "environment": {
            "input": {
                "placeholder": "Select an environment",
            },
            "widget": {
                "label_from_instance": lambda obj: f"{obj.value} - {obj.description}",
            },
        },
    }


class EditMetaModal(ModalForm[EditMetaFormSlack]):
    open_action: str = "open_modal_incident_edit"
    update_action: str = "update_modal_incident_edit"
    push_action: str = "push_modal_incident_edit"
    open_shortcut = "modal_edit"
    callback_id: str = "incident_edit_incident"

    form_class = EditMetaFormSlack

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks = self.get_form_class()(
            initial={
                "title": incident.title,
                "description": incident.description,
                "environment": incident.environment,
            },
        ).slack_blocks()

        return View(
            type="modal",
            title=f"Update incident #{incident.id}"[:24],
            submit="Update incident"[:24],
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
                "initial": {
                    "title": incident.title,
                    "description": incident.description,
                    "environment": incident.environment,
                }
            },
        )
        if slack_form is None:
            return
        form: EditMetaFormSlack = slack_form.form
        if len(form.cleaned_data) == 0:
            # XXX We should have a prompt for empty forms

            return
        update_kwargs: dict[str, Any] = {}
        for changed_key in form.changed_data:
            if changed_key == "environment":
                update_kwargs[f"{changed_key}_id"] = form.cleaned_data[changed_key].id
            if changed_key in {"description", "title"}:
                update_kwargs[changed_key] = form.cleaned_data[changed_key]
        if len(update_kwargs) == 0:
            logger.warning("No update to incident status")
            return
        self._trigger_incident_workflow(incident, user, **update_kwargs)

    @staticmethod
    def _trigger_incident_workflow(
        incident: Incident, user: User, **kwargs: Any
    ) -> None:
        incident.create_incident_update(created_by=user, **kwargs)


modal_edit = EditMetaModal()
