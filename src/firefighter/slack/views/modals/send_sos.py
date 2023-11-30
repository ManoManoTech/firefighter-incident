from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms
from django.forms.models import ModelChoiceIterator
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.slack.forms.sos_form import SosForm
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.views.modals.base_modal.base import ModalForm
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User
    from firefighter.slack.models.sos import Sos
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


def sos_label(obj: Sos) -> str:
    return f"{obj.name}  ({obj.usergroup_slack_fmt} in #{obj.conversation.name})"


class SendSosFormSlack(SosForm):
    slack_fields: SlackFormAttributesDict = {
        "sos": {
            "input": {
                "placeholder": "Select your SOS",
            },
            "widget": {
                "label_from_instance": sos_label,
            },
        },
    }


class SendSosModal(IncidentSelectableModalMixin, ModalForm[SendSosFormSlack]):
    open_action: str = "open_modal_incident_send_sos"

    update_action: str = "update_modal_incident_send_sos"
    push_action: str = "push_modal_incident_send_sos"
    callback_id: str = "incident_send_sos"

    form_class = SendSosFormSlack

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks: list[Block] = [
            SectionBlock(
                text=":bulb: You are about to request help from SREs, in their dedicated Slack channel.\nChoose the right train to alert the right people."
            )
        ]
        sos_form = self.get_form_class()()
        sos_field = sos_form.form.fields["sos"]
        if not isinstance(sos_field, forms.ModelChoiceField):
            raise TypeError("sos field must be a ModelChoiceField")
        sos_field_choices = sos_field.choices
        if not isinstance(sos_field_choices, list | ModelChoiceIterator):
            raise TypeError("sos field choices must be a list or a ModelChoiceIterator")
        has_sos_options = len(sos_field_choices) > 0
        if has_sos_options:
            blocks.extend(sos_form.slack_blocks())
        else:
            blocks.append(
                SectionBlock(
                    text=":warning: No SOS configured in the database! :warning:\nAdministrator action is needed. Please raise the issue."
                )
            )
            logger.error(
                "No SOS configured in the database! Please SOSes in the back-office."
            )
        blocks.extend((slack_block_separator(), slack_block_footer()))
        return View(
            type="modal",
            title=f"Get help for #{incident.id}"[:24],
            submit="Send SOS"[:24] if has_sos_options else None,
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    def handle_modal_fn(  # type: ignore
        self, ack: Ack, body: dict[str, Any], incident: Incident, user: User
    ):
        slack_form = self.handle_form_errors(
            ack, body, forms_kwargs={}, ack_on_success=False
        )
        if slack_form is None:
            return
        form: SendSosFormSlack = slack_form.form
        if len(form.cleaned_data) == 0:
            # XXX We should have a prompt for empty forms
            return
        try:
            self._send_incident_sos(incident, form.cleaned_data["sos"], user)
            ack()
        except SlackApiError:
            logger.exception(f"Error sending SOS for #{incident.id}")
            # XXX Better strategy for errors?
            ack()

    def get_select_modal_title(self) -> str:
        return "Send SOS"

    def get_select_title(self) -> str:
        return "Select a critical incident for which you need help"

    @staticmethod
    def _send_incident_sos(incident: Incident, sos: Sos, user: User) -> None:
        from firefighter.slack.messages.slack_messages import (  # noqa: PLC0415
            SlackMessagesSOS,
        )

        sos.conversation.send_message_and_save(
            SlackMessagesSOS(incident=incident, usergroup=sos.usergroup_slack_fmt)
        )
        incident.create_incident_update(
            message=f"Asked for SRE help in #{sos.conversation.name}",
            event_type="send_sos",
            created_by=user,
        )


modal_send_sos = SendSosModal()
