from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from django import forms
from django.db.models import Model
from slack_sdk.models.views import View

from firefighter.firefighter.utils import get_in
from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.signals import create_incident_conversation
from firefighter.slack.views.modals.base_modal.base import ModalForm
from firefighter.slack.views.modals.base_modal.form_utils import (
    SlackFormJSONEncoder,
    slack_view_submission_to_dict,
)
from firefighter.slack.views.modals.base_modal.modal_utils import (
    push_modal,
    update_modal,
)
from firefighter.slack.views.modals.opening.types import OpeningData

if TYPE_CHECKING:
    from slack_bolt import BoltRequest
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


T = TypeVar("T", bound=CreateIncidentFormBase)


class SetIncidentDetails(ModalForm[T], Generic[T]):
    callback_id: str
    push_action: str
    title: str = "Open an incident"
    submit_text: str = "Save details"
    form_class: type[T]
    id: str

    def __init__(self) -> None:
        if hasattr(self, "id"):
            self.push_action = f"push_{self.id}"
        super().__init__()

    def build_modal_fn(
        self, open_incident_context: OpeningData | None = None, **kwargs: Any
    ) -> View:
        open_incident_context = open_incident_context or {}
        details_form_data: dict[str, Any] = (
            open_incident_context.get("details_form_data") or {}
        )
        for field_name, field in self.form_class.base_fields.items():
            if (
                isinstance(field, forms.ModelChoiceField)
                and field_name in details_form_data
                and not isinstance(details_form_data[field_name], Model)
                and field.queryset is not None
                and field.queryset.model
                and hasattr(field.queryset.model, "DoesNotExist")
            ):
                try:
                    details_form_data[field_name] = field.queryset.get(
                        pk=details_form_data[field_name]
                    )
                except field.queryset.model.DoesNotExist:
                    details_form_data[field_name] = None

        return View(
            type="modal",
            title=self.title[:24],
            submit=self.submit_text[:24],
            close="Close details",
            callback_id=self.callback_id,
            blocks=self.get_form_class()(initial=details_form_data, open_incident_context=open_incident_context, **kwargs).slack_blocks(),
            private_metadata=json.dumps(
                open_incident_context, cls=SlackFormJSONEncoder
            ),
        )

    def handle_modal_fn(  # type: ignore
        self,
        ack: Ack,
        body: dict[str, Any],
        user: User | None = None,
    ):
        """Handle response from /incident open modal."""
        private_metadata: dict[str, Any] = json.loads(
            body.get("view", {}).get("private_metadata", {})
        )
        priority = private_metadata.get("details_form_data", {}).get("priority", None)
        if priority is not None:
            priority = Priority.objects.get(pk=priority)

        slack_form = self.get_form_class()(
            data={**slack_view_submission_to_dict(body), "priority": priority},
            open_incident_context=private_metadata,
        )
        form: T = slack_form.form
        if form.is_valid():
            ack()
            skip_form = False
        else:
            ack(
                response_action="errors",
                errors={
                    k: self._concat_validation_errors_msg(v)
                    for k, v in form.errors.as_data().items()
                },
            )
            skip_form = True

        if skip_form:
            return
        # ruff: noqa: PLC0415
        from firefighter.slack.views.modals.open import modal_open

        if "priority" in private_metadata and isinstance(
            private_metadata["priority"], str
        ):
            private_metadata["priority"] = Priority.objects.get(
                pk=private_metadata["priority"]
            )
        data = OpeningData(
            details_form_data=cast("dict[str, Any]", form.data),
            impact_form_data=private_metadata.get("impact_form_data"),
            incident_type=private_metadata.get("incident_type"),
            response_type=private_metadata.get("response_type"),
            priority=private_metadata.get("priority"),
        )
        view = modal_open.build_modal_fn(open_incident_context=data, user=user)
        view.private_metadata = json.dumps(data, cls=SlackFormJSONEncoder)

        update_modal(
            view=view,
            trigger_id=get_in(body, ["trigger_id"]),
            view_id=get_in(body, ["view", "root_view_id"]),
        )

    @staticmethod
    def _trigger_incident_workflow(
        incident: Incident,
    ) -> None:
        create_incident_conversation.send(
            "incident_created",
            incident=incident,
        )

    def _handle_action_push(
        self,
        request: BoltRequest,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        body = request.body
        ack: Ack = request.context.ack
        data: OpeningData = (
            json.loads(body.get("actions", [{}])[0].get("value", {})) or {}  # type: ignore
        )

        view = self.build_modal_fn(open_incident_context=data)
        view.private_metadata = json.dumps(data, cls=SlackFormJSONEncoder)
        ack()
        push_modal(view=view, body=body)
