from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
    Block,
    ContextBlock,
    DividerBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.close_incident import CloseIncidentForm
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import ModalForm
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)
from firefighter.slack.views.modals.postmortem import PostMortemModal
from firefighter.slack.views.modals.update_status import UpdateStatusModal
from firefighter.slack.views.modals.utils import (
    get_close_modal_view,
    handle_close_modal_callback,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, User
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


class CloseIncidentFormSlack(CloseIncidentForm):
    slack_fields: SlackFormAttributesDict = {
        "message": {
            "input": {
                "multiline": True,
                "placeholder": "Please describe the new status for the incident.\nE.g: Fixed with instance reboot.",
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


class CloseModal(
    IncidentSelectableModalMixin,
    ModalForm[CloseIncidentFormSlack],
):
    open_action: str = "close_incident"
    open_shortcut = "close_incident"
    callback_id: str = "incident_close"

    form_class = CloseIncidentFormSlack

    def build_modal_fn(
        self, body: dict[str, Any], incident: Incident, **kwargs: Any
    ) -> View:
        # Check if closure reason modal should be shown instead
        closure_view = get_close_modal_view(body, incident, **kwargs)
        if closure_view:
            return closure_view

        can_be_closed, reasons = incident.can_be_closed
        if not can_be_closed:
            reason_blocks: list[Block] = []
            for reason in reasons:
                if reason[0] == "MISSING_REQUIRED_KEY_EVENTS":
                    reason_blocks += [
                        SectionBlock(
                            text=":warning: *Missing required key events* :warning:"
                        ),
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=reason[1]
                                    + "\nPlease fill the required key events of the incident before closing it."
                                )
                            ]
                        ),
                    ]
                elif reason[0] == "STATUS_NOT_POST_MORTEM":
                    reason_blocks += [
                        SectionBlock(
                            text=f":warning: *Status is not _{IncidentStatus.POST_MORTEM.label}_* :warning:\n"
                        ),
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=f"This status is required. Please update the status to _{IncidentStatus.POST_MORTEM.label}_ and *fill the post-mortem on Confluence* before closing the incident."
                                )
                            ]
                        ),
                        ActionsBlock(
                            elements=[
                                (
                                    ButtonElement(
                                        text="Fill the post-mortem on Confluence",
                                        action_id="open_link",
                                        url=incident.postmortem_for.page_edit_url,
                                        style="primary",
                                    )
                                    if hasattr(incident, "postmortem_for")
                                    else ButtonElement(
                                        text="Create the post-mortem",
                                        action_id=str(PostMortemModal.push_action),
                                        value=str(incident.id),
                                        style="primary",
                                    )
                                ),
                                ButtonElement(
                                    text="Update status",
                                    action_id=UpdateStatusModal.push_action,
                                    value=str(incident.id),
                                ),
                            ]
                        ),
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=f":bulb: You can also publish an update and change the status of the incident with `{settings.SLACK_INCIDENT_COMMAND} update`. You can also use `{settings.SLACK_INCIDENT_COMMAND} postmortem` to access or create your post-mortem."
                                )
                            ]
                        ),
                    ]
                elif reason[0] == "STATUS_NOT_MITIGATED":
                    reason_blocks += [
                        SectionBlock(
                            text=f":warning: *Status is not _{IncidentStatus.MITIGATED.label}_* :warning:\n"
                        ),
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=f"You can only close an incident when its status is _{IncidentStatus.MITIGATED.label}_ or _{IncidentStatus.POST_MORTEM.label}_. The _{IncidentStatus.POST_MORTEM.label}_ status is not mandatory for this incident."
                                )
                            ]
                        ),
                        ActionsBlock(
                            elements=[
                                ButtonElement(
                                    text="Update status",
                                    action_id=UpdateStatusModal.push_action,
                                    value=str(incident.id),
                                    style="primary",
                                ),
                            ]
                        ),
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=f":bulb: You can also publish an update and change the status of the incident with `{settings.SLACK_INCIDENT_COMMAND} update`"
                                )
                            ]
                        ),
                    ]

            return View(
                type="modal",
                title=f"Close incident #{incident.id}"[:24],
                submit=None,
                callback_id=self.callback_id,
                private_metadata=str(incident.id),
                blocks=[
                    SectionBlock(
                        text=":x:  This incident can't be closed yet.\n:point_right:  Please fix the following issues before closing it.",
                    ),
                    DividerBlock(),
                    *reason_blocks,
                    slack_block_separator(),
                    slack_block_footer(),
                ],
            )
        logger.debug(body)
        context_elements = [
            MarkdownTextObject(
                text=":warning: You're about to close this incident which will archive the Slack channel and execute any post-incident actions.\nPlease review the incident details below."
            ),
        ]
        if hasattr(incident, "postmortem_for"):
            context_elements.append(
                MarkdownTextObject(
                    text=f":page_facing_up: Make sure <{incident.postmortem_for.page_url}|your post-mortem> is complete before closing the incident."
                )
            )
        blocks: list[Block] = [
            ContextBlock(elements=context_elements),
            *self.get_form_class()(
                initial=self._get_initial_form_values(incident)
            ).slack_blocks(),
            slack_block_separator(),
            slack_block_footer(),
        ]

        return View(
            type="modal",
            title=f"Close incident #{incident.id}"[:24],
            submit="Close incident"[:24],
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    def handle_modal_fn(  # type: ignore[override]
        self, ack: Ack, body: dict[str, Any], incident: Incident, user: User
    ) ->  bool | None:
        """Handle response from /incident close modal."""
        # Check if this should be handled by closure reason modal
        closure_result = handle_close_modal_callback(ack, body, incident, user)
        if closure_result is not None:
            return closure_result
        slack_form = self.handle_form_errors(
            ack, body, forms_kwargs={"initial": self._get_initial_form_values(incident)}
        )
        if slack_form is None:
            return None
        form = slack_form.form
        # If fields haven't changed, don't include them in the update.
        update_kwargs = {}
        for changed_key in form.changed_data:
            if changed_key == "incident_category":
                update_kwargs["incident_category_id"] = form.cleaned_data[changed_key].id
            if changed_key in {"description", "title", "message"}:
                update_kwargs[changed_key] = form.cleaned_data[changed_key]
        # Check can close
        can_close, reasons = incident.can_be_closed
        if not can_close:
            logger.warning(
                f"Tried to close an incident that can't be closed yet! Aborting. Incident #{incident.id}. Reasons: {reasons}"
            )
            respond(
                body=body,
                text=f"It looks like this incident #{incident.id} could not be closed.\nReasons: {reasons}.\nPlease tell @pulse (#tech-pe-pulse) if you think this is an error.",
            )
            return False
        self._trigger_incident_workflow(incident, user, update_kwargs)
        return None

    def get_select_modal_title(self) -> str:
        return "Close incident"

    def get_select_title(self) -> str:
        return "Select a critical incident to close"

    @staticmethod
    def _get_initial_form_values(incident: Incident) -> dict[str, Any]:
        return {
            "title": incident.title,
            "description": incident.description,
            "incident_category": incident.incident_category,
        }

    @staticmethod
    def _trigger_incident_workflow(
        incident: Incident, user: User, update_kwargs: dict[str, Any]
    ) -> None:
        incident.create_incident_update(
            created_by=user,
            status=IncidentStatus.CLOSED,
            **update_kwargs,
        )


modal_close = CloseModal()
