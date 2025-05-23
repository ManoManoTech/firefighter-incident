from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from slack_sdk.models.blocks.blocks import SectionBlock
from slack_sdk.models.views import View

from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.views.modals.base_modal.base import ModalForm

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, Priority, Severity
    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


def priority_label(obj: Severity | Priority) -> str:
    return f"{obj.emoji}  {obj.name} - {obj.description}"


class UpdateStatusFormSlack(UpdateStatusForm):
    slack_fields: SlackFormAttributesDict = {
        "message": {
            "input": {
                "multiline": True,
                "placeholder": "Please describe the new status for the incident.\nE.g: Fixed with instance reboot.",
            },
            "block": {"hint": None},
        },
        "priority": {
            "input": {
                "placeholder": "Select a priority",
            },
            "widget": {
                "post_block": (
                    SectionBlock(
                        text=f"_<{settings.SLACK_SEVERITY_HELP_GUIDE_URL}|How to choose the priority?>_"
                    )
                    if settings.SLACK_SEVERITY_HELP_GUIDE_URL
                    else None
                ),
                "label_from_instance": priority_label,
            },
        },
        "component": {
            "input": {
                "placeholder": "Select affected issue category",
            }
        },
    }


class UpdateStatusModal(ModalForm[UpdateStatusFormSlack]):
    open_action: str = "open_modal_incident_update_status"
    update_action: str = "update_modal_incident_update_status"
    push_action: str = "push_modal_incident_update_status"
    open_shortcut = "update_incident_status"
    callback_id: str = "incident_update_status"

    form_class = UpdateStatusFormSlack

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks = self.get_form_class()(
            initial={
                "status": incident.status,
                "priority": incident.priority,
                "component": incident.component,
            }
        ).slack_blocks()
        blocks.append(slack_block_separator())
        blocks.append(slack_block_footer())
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
                    "status": incident.status,
                    "priority": incident.priority,
                    "component": incident.component,
                }
            },
        )
        if slack_form is None:
            return
        form: UpdateStatusFormSlack = slack_form.form
        if len(form.cleaned_data) == 0:
            # XXX We should have a prompt for empty forms
            return
        update_kwargs: dict[str, Any] = {}
        for changed_key in form.changed_data:
            if changed_key in {"component", "priority"}:
                update_kwargs[f"{changed_key}_id"] = form.cleaned_data[changed_key].id
            if changed_key in {"description", "title", "message", "status"}:
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


modal_update_status = UpdateStatusModal()
