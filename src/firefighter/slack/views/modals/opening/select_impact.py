from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Never, cast

from django import forms
from django.conf import settings
from django.db.models import Model, QuerySet
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import (
    ContextBlock,
    DividerBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.firefighter.utils import get_in
from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.models.impact import ImpactType
from firefighter.incidents.models.priority import Priority
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.modals import modal_open
from firefighter.slack.views.modals.base_modal.base import ModalForm
from firefighter.slack.views.modals.base_modal.form_utils import (
    SlackForm,
    SlackFormAttributesDict,
    SlackFormJSONEncoder,
)
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)
from firefighter.slack.views.modals.base_modal.modal_utils import (
    push_modal,
    update_modal,
)
from firefighter.slack.views.modals.opening.types import OpeningData, ResponseType

if TYPE_CHECKING:
    from slack_bolt import BoltRequest
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.user import User

app = SlackApp()
logger = logging.getLogger(__name__)
BASE_URL: str = settings.BASE_URL
SLACK_APP_EMOJI: str = settings.SLACK_APP_EMOJI


class SelectImpactFormSlack(SelectImpactForm):
    slack_fields: SlackFormAttributesDict = {"customer_impact": {}}


class SelectImpactModal(
    IncidentSelectableModalMixin,
    ModalForm[SelectImpactFormSlack],
):
    """TODO: The detailed impacts selected should be saved on the incident."""

    open_action: str = "open_incident_select_impact"
    open_shortcut: str = "open_incident_select_impact"
    push_action: str = "push_incident_select_impact"
    callback_id: str = "incident_select_impact"

    form_class: type[SelectImpactFormSlack] = SelectImpactFormSlack

    def build_modal_fn(
        self, body: dict[str, Any], open_incident_context: OpeningData, **kwargs: Never
    ) -> View:
        initial_form_values_impact = open_incident_context.get("impact_form_data", {})
        if initial_form_values_impact:
            for field_name, field in self.form_class().fields.items():
                if (
                    isinstance(field, forms.ModelChoiceField)
                    and field_name in initial_form_values_impact
                    and not isinstance(initial_form_values_impact[field_name], Model)
                    and field.queryset is not None
                    and hasattr(field.queryset.model, "DoesNotExist")
                ):
                    try:
                        initial_form_values_impact[field_name] = field.queryset.get(
                            pk=initial_form_values_impact[field_name]
                        )
                    except field.queryset.model.DoesNotExist:
                        initial_form_values_impact[field_name] = None  # type: ignore
        blocks = [
            SectionBlock(
                text=f"{SLACK_APP_EMOJI} Define the impact(s) to find the incident priority (<https://manomano.atlassian.net/wiki/spaces/TC/pages/4024500413/Priority+levels|documentation>):"
            ),
            *self.get_form_class()(initial=initial_form_values_impact).slack_blocks(
                "section_accessory"
            ),
        ]
        priority_data = open_incident_context.get("priority")

        if open_incident_context and priority_data:
            if not isinstance(priority_data, Priority):
                priority = Priority.objects.get(pk=priority_data)
            elif isinstance(priority_data, Priority):
                priority = priority_data
            else:
                err_msg = f"Invalid priority data: {priority_data}"  # type: ignore[unreachable]
                raise TypeError(err_msg)
            process = ":slack: Slack :jira_new: Jira ticket" if open_incident_context.get("response_type") == "critical" else ":jira_new: Jira ticket"

            impact_descriptions = self.extract_descriptions(open_incident_context)

            blocks.extend((
                DividerBlock(),
                ContextBlock(
                    elements=[
                        MarkdownTextObject(
                            text=(
                                f":dart: Selected priority: *{priority} - {priority.description}*\n"
                                f"⏱️ SLA: {priority.sla}\n"
                                f":gear: Process: {process}\n"
                                f":pushpin: Selected impacts:\n"
                                f"{impact_descriptions}\n"
                            )
                        )
                    ]
                )
            ))

        return View(
            type="modal",
            callback_id=self.callback_id,
            title="Incident Impact"[:24],
            private_metadata=str(body["trigger_id"]),
            blocks=blocks,
            submit="Save impacts",
        )

    def extract_descriptions(self, open_incident_context: OpeningData) -> str:
        impact_form_data = open_incident_context.get("impact_form_data", {})
        impact_descriptions = ""
        if impact_form_data:
            for value in impact_form_data.values():
                # Filter out "no impact" levels using the value field instead of name
                if not ((hasattr(value, "value") and value.value == "NO") or value.name == "NO" or not value.description):
                    if hasattr(value, "impact_type_id") and value.impact_type_id:
                        impact_type = ImpactType.objects.get(pk=value.impact_type_id)
                        if impact_type:
                            impact_descriptions += f"\u00A0\u00A0 :exclamation: {impact_type} - {value}\n"
                    for line in str(value.description).splitlines():
                        # Skip empty lines or lines with only dashes/whitespace
                        if line.strip() and line.strip() != "-":
                            impact_descriptions += f"\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0 • {line}\n"
        return impact_descriptions

    def handle_modal_fn(  # type: ignore
        self,
        ack: Ack,
        body: dict[str, Any],
        user: User | None = None,
    ) -> None:
        form = self.handle_form_errors(ack, body, {})
        if form is None:
            return

        private_metadata = self._update_private_metadata(body, form)
        view = modal_open.build_modal_fn(
            open_incident_context=private_metadata, user=user
        )
        view.private_metadata = json.dumps(private_metadata, cls=SlackFormJSONEncoder)
        update_modal(
            view=view,
            trigger_id=get_in(body, ["trigger_id"]),
            view_id=get_in(body, ["view", "root_view_id"]),
        )

    def _handle_action_push(
        self,
        request: BoltRequest,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        body = request.body
        data = cast(
            "OpeningData", json.loads(body.get("actions", [{}])[0].get("value", {})) or {}
        )
        view = self.build_modal_fn(body, open_incident_context=data)
        request.context.ack()

        view.private_metadata = json.dumps(data, cls=SlackFormJSONEncoder)
        push_modal(view=view, body=body)

    @app.block_action(re.compile(r"set_impact_type.+"))
    @staticmethod
    def handle_select_impact(ack: Ack, body: dict[str, Any], **kwargs: Any) -> None:
        modal = SelectImpactModal()
        form = modal.handle_form_errors(ack, body, {})
        if form is None:
            return

        private_metadata = SelectImpactModal._update_private_metadata(body, form)
        view = modal.build_modal_fn(body, open_incident_context=private_metadata)
        view.private_metadata = json.dumps(private_metadata, cls=SlackFormJSONEncoder)
        update_modal(
            view=view,
            body=body,
        )

    @staticmethod
    def _calculate_proposed_incident_type(
        suggested_priority_value: int,
    ) -> ResponseType:
        try:
            priority = Priority.objects.get(value=suggested_priority_value)
            # Use priority recommendation if available
            if priority.recommended_response_type:
                return cast("ResponseType", priority.recommended_response_type)
        except Priority.DoesNotExist:
            logger.warning(f"Priority with value {suggested_priority_value} does not exist")

        # Fallback logic: P1/P2/P3 = critical, P4/P5 = normal
        return "critical" if suggested_priority_value < 4 else "normal"

    @staticmethod
    def _update_private_metadata(
        body: dict[str, Any], form: SlackForm[SelectImpactFormSlack]
    ) -> OpeningData:
        private_metadata_raw: dict[str, Any] = json.loads(
            body.get("view", {}).get("private_metadata", {})
        )

        # Convert the form fields str to Models
        for field_name, field in form.form.fields.items():
            if (
                isinstance(field, forms.ModelChoiceField)
                and field_name in form.form.data
                and not isinstance(form.form.data[field_name], Model)
                and field.queryset is not None
            ):
                queryset = cast("QuerySet[ImpactLevel]", field.queryset)
                try:
                    form.form.data[field_name] = queryset.get(  # type: ignore
                        pk=form.form.data[field_name]
                    )
                except queryset.model.DoesNotExist:
                    form.form.data[field_name] = None  # type: ignore
        suggested_priority_value = form.form.suggest_priority_from_impact()

        # If no impacts are selected (all set to "NO"), don't set priority/response_type
        if suggested_priority_value == 6:  # LevelChoices.NONE.priority
            return OpeningData(
                priority=None,
                response_type=None,
                impact_form_data=cast("dict[str, Any]", form.form.data),
                details_form_data=private_metadata_raw.get("details_form_data", {}),
                incident_type=private_metadata_raw.get("incident_type"),
            )

        try:
            priority = Priority.objects.get(value=suggested_priority_value)
        except Priority.DoesNotExist as err:
            logger.exception(
                f"Priority with value {suggested_priority_value} does not exist"
            )
            # Fallback to default priority (assuming P3 exists)
            fallback_priority = Priority.objects.filter(value__gte=3).first()
            if not fallback_priority:
                # If no priority exists, create a minimal fallback
                logger.exception("No priority found in database")
                raise ValueError("No priority configuration found in database") from err
            priority = fallback_priority

        return OpeningData(
            priority=priority,
            response_type=SelectImpactModal._calculate_proposed_incident_type(
                suggested_priority_value
            ),
            impact_form_data=cast("dict[str, Any]", form.form.data),
            details_form_data=private_metadata_raw.get("details_form_data", {}),
            incident_type=private_metadata_raw.get("incident_type"),
        )


modal_select_impact = SelectImpactModal()
