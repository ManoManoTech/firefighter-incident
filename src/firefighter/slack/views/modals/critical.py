from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from slack_sdk.models.blocks.blocks import SectionBlock
from slack_sdk.models.views import View

from firefighter.incidents.forms.create_incident import CreateIncidentForm
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.modals.base_modal.base import ModalForm

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Priority, Severity
    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

app = SlackApp()
logger = logging.getLogger(__name__)


def priority_label(obj: Severity | Priority) -> str:
    return f"{obj.emoji}  {obj.name} - {obj.description}"


class CriticalFormSlack(CreateIncidentForm):
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
        "component": {
            "input": {
                "placeholder": "Select affected component",
            }
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
    }


class CriticalModal(ModalForm[CriticalFormSlack]):
    open_action: str = "open_modal_incident_critical"
    open_shortcut = "modal_critical"
    callback_id: str = "incident_critical"

    form_class = CriticalFormSlack

    def build_modal_fn(self, **kwargs: Any) -> View:
        form_instance = self.get_form_class()()
        blocks = form_instance.slack_blocks()

        return View(
            type="modal",
            title="Open a critical incident"[:24],
            submit="Create the incident"[:24],
            callback_id=self.callback_id,
            blocks=blocks,
            clear_on_close=False,
            close=None,
        )

    def handle_modal_fn(  # type: ignore
        self, ack: Ack, body: dict[str, Any], user: User
    ) -> None :
        slack_form = self.handle_form_errors(
            ack, body, forms_kwargs={},
        )

        if slack_form is None:
            return

        form = slack_form.form

        try:
            if hasattr(form, "trigger_incident_workflow") and callable(
                form.trigger_incident_workflow
            ):
                form.trigger_incident_workflow(
                    creator=user,
                    impacts_data=None,
                )
        except:  # noqa: E722
            logger.exception("Error triggering incident workflow")
            # XXX warn the user via DM!

        if len(form.cleaned_data) == 0:
            logger.warning("Form is empty, no data captured.")
            return


modal_critical = CriticalModal()
