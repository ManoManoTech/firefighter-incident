from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.apps import apps
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import RadioButtonsElement
from slack_sdk.models.blocks.blocks import Block, DividerBlock, InputBlock, SectionBlock
from slack_sdk.models.views import View

from firefighter.firefighter.utils import get_in
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, User
if apps.is_installed("firefighter.pagerduty"):
    from firefighter.pagerduty.models import PagerDutyIncident, PagerDutyService

logger = logging.getLogger(__name__)


class OnCallModal(IncidentSelectableModalMixin, SlackModal):
    open_action: str = "open_modal_trigger_oncall"
    callback_id: str = "incident_oncall_trigger"

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        """XXX Should get an incident ID instead of an incident."""
        previous_pd_incidents = PagerDutyIncident.objects.filter(
            incident_id=incident.id
        )

        pd_services = PagerDutyService.objects.exclude(
            pagerdutyincident__in=previous_pd_incidents,
        ).filter(ignore=False)
        pd_options = [Option(value=str(s.id), label=s.summary) for s in pd_services]

        blocks: list[Block] = [
            SectionBlock(
                text=f"You are about to trigger on-call for incident #{incident.id}. Please select the on-call line that you want to trigger."
            ),
            DividerBlock(),
            (
                InputBlock(
                    block_id="oncall_service",
                    label="Select on-call line",
                    element=RadioButtonsElement(
                        action_id="select_oncall_service", options=pd_options
                    ),
                )
                if len(pd_options) > 0
                else SectionBlock(
                    text=":warning: No PagerDuty services in the database! :warning:\nAdministrator action is needed."
                )
            ),
        ]

        if len(previous_pd_incidents) > 0:
            already_existing_text = [
                f"- <{s.service.web_url}|{s.service.summary}>: <{s.web_url}|_{s.summary}_>\n"
                for s in previous_pd_incidents
            ]
            blocks.extend((
                DividerBlock(),
                SectionBlock(
                    text=f":warning: There are already some on-call lines that have been triggered and can not be triggered again:\n {''.join(already_existing_text)}"
                ),
            ))

        return View(
            type="modal",
            title="Trigger on-call"[:24],
            submit="Trigger on-call"[:24] if len(pd_options) > 0 else None,
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    @staticmethod
    def handle_modal_fn(ack: Ack, body: dict[str, Any], incident: Incident, user: User):  # type: ignore
        ack()

        pd_service_id = get_in(
            body,
            "view.state.values.oncall_service.select_oncall_service.selected_option.value",
        )
        # TODO Fix the dependency on PagerDuty app
        # ruff: noqa: PLC0415
        from firefighter.pagerduty.tasks.trigger_oncall import trigger_oncall

        service: PagerDutyService | None = PagerDutyService.objects.get(
            id=pd_service_id
        )
        if service is None:
            raise ValueError("Service not found")

        try:
            pd_incident = trigger_oncall(
                oncall_service=service,
                incident_key=incident.canonical_name
                + "-"
                + str(service.pagerduty_id.lower()),
                title=incident.title,
                details=incident.description,
                incident_id=incident.id,
                conference_url=(incident.slack_channel_url or incident.status_page_url),
                triggered_by=user,
            )
        except Exception as e:  # TODO better exception handling
            logger.exception("Could not trigger on-call from modal submission.")
            respond(body, text=f"Unexpected error when calling PagerDuty! Error: {e}")
            return

        incident.create_incident_update(
            message=f":phone:  Triggered {service.name} on-call on PagerDuty (<{pd_incident.web_url}|see incident on PagerDuty>)  :phone:",
            event_type="trigger_oncall",
            created_by=user,
        )

    def get_select_modal_title(self) -> str:
        return "Trigger on-call"

    def get_select_title(self) -> str:
        return "Select a critical incident to trigger on-call for"


modal_trigger_oncall = OnCallModal()
