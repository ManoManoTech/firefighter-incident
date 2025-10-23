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
                "placeholder": "Select environments (multiple allowed)",
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
        from firefighter.incidents.models import Environment  # noqa: PLC0415

        # Get all environments from custom_fields, fallback to single environment
        environments_values = incident.custom_fields.get("environments", [])
        if environments_values:
            # Convert environment value strings to Environment objects
            environments = list(
                Environment.objects.filter(value__in=environments_values)
            )
        else:
            # Fallback to single environment field
            environments = [incident.environment] if incident.environment else []

        blocks = self.get_form_class()(
            initial={
                "title": incident.title,
                "description": incident.description,
                "environment": environments,
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
        from firefighter.incidents.models import Environment  # noqa: PLC0415

        # Get current environments for initial comparison
        environments_values = incident.custom_fields.get("environments", [])
        if environments_values:
            current_environments = list(
                Environment.objects.filter(value__in=environments_values)
            )
        else:
            current_environments = (
                [incident.environment] if incident.environment else []
            )

        slack_form = self.handle_form_errors(
            ack,
            body,
            forms_kwargs={
                "initial": {
                    "title": incident.title,
                    "description": incident.description,
                    "environment": current_environments,
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
        update_custom_fields = False

        for changed_key in form.changed_data:
            if changed_key == "environment":
                # Handle multiple environments
                environments = form.cleaned_data[changed_key]
                if environments:
                    # Select highest priority environment (lowest order) for main field
                    primary_env = min(environments, key=lambda env: env.order)
                    update_kwargs["environment_id"] = primary_env.id

                    # Update custom_fields with all selected environments
                    custom_fields = incident.custom_fields.copy()
                    custom_fields["environments"] = [env.value for env in environments]
                    incident.custom_fields = custom_fields
                    update_custom_fields = True
            if changed_key in {"description", "title"}:
                update_kwargs[changed_key] = form.cleaned_data[changed_key]

        if len(update_kwargs) == 0 and not update_custom_fields:
            logger.warning("No update to incident")
            return

        # Save custom_fields if updated
        if update_custom_fields:
            incident.save(update_fields=["custom_fields"])

        # Create incident update for tracked fields
        if update_kwargs:
            self._trigger_incident_workflow(incident, user, **update_kwargs)

    @staticmethod
    def _trigger_incident_workflow(
        incident: Incident, user: User, **kwargs: Any
    ) -> None:
        incident.create_incident_update(created_by=user, **kwargs)


modal_edit = EditMetaModal()
