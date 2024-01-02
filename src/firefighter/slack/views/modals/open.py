from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, cast

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from slack_sdk.models.blocks.basic_components import MarkdownTextObject, Option
from slack_sdk.models.blocks.block_elements import ButtonElement, StaticSelectElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
    Block,
    ContextBlock,
    DividerBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.firefighter.utils import is_during_office_hours
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_incident_context import get_user_from_context
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.form_utils import SlackFormJSONEncoder
from firefighter.slack.views.modals.base_modal.modal_utils import update_modal
from firefighter.slack.views.modals.opening.check_current_incidents import (
    CheckCurrentIncidentsModal,
)
from firefighter.slack.views.modals.opening.details.critical import OpeningCriticalModal
from firefighter.slack.views.modals.opening.types import OpeningData, ResponseType

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails

app = SlackApp()
logger = logging.getLogger(__name__)

SLACK_SEVERITY_HELP_GUIDE_URL: str | None = settings.SLACK_SEVERITY_HELP_GUIDE_URL


INCIDENT_TYPES: dict[ResponseType, dict[str, dict[str, Any]]] = {
    "critical": {
        "critical": {
            "label": "Critical",
            "slack_form": OpeningCriticalModal,
        },
    },
}


class OpenModal(SlackModal):
    open_action: str = "open_incident"
    open_shortcut = "open_incident"
    callback_id: str = "incident_open"

    def build_modal_fn(self, open_incident_context: OpeningData | None = None, user: User | None = None) -> View:  # type: ignore
        if user is None:
            raise ValueError("user is required for OpenModal!")
        open_incident_context = open_incident_context or OpeningData()
        # 1. Check if impact form is good
        is_impact_form_valid: bool = self._check_impact_form(open_incident_context)

        # 2. Check if we have a normal incident type
        incident_type_value: str | None = open_incident_context.get(
            "incident_type", None
        )

        # 3. Check if details form is good
        (
            is_details_form_valid,
            details_form_class,
            details_form_modal_class,
            details_form,
        ) = self._check_details_form(open_incident_context, incident_type_value)

        # Add priority field to details form from priority
        # XXX Priority should be on both impact_form_data and details_form_data and not in OpeningData
        if (
            open_incident_context.get("priority")
            and "priority" in open_incident_context
            and open_incident_context["priority"]
        ):
            if (
                "details_form_data" not in open_incident_context
                or open_incident_context["details_form_data"] is None
            ):
                open_incident_context["details_form_data"] = {}
            assert open_incident_context["details_form_data"] is not None  # noqa: S101
            open_incident_context["details_form_data"][
                "priority"
            ] = open_incident_context["priority"]

        # Make blocks with all this context
        intro_blocks = self.get_intro_blocks()
        set_impacts_blocks = self.get_set_impact_blocks(
            open_incident_context, impact_form_done=is_impact_form_valid
        )
        choose_response_type_blocks = self._build_response_type_blocks(
            open_incident_context
        )
        select_incident_type_blocks = self.get_select_incident_type_blocks(
            open_incident_context, incident_type_value
        )
        set_details_blocks = self.get_set_details_blocks(
            open_incident_context,
            details_form_done=is_details_form_valid,
            details_form_modal_class=details_form_modal_class,
        )

        # Can we submit?
        can_submit: bool = is_impact_form_valid and is_details_form_valid
        done_review_blocks = self.get_done_review_blocks(
            open_incident_context,
            user,
            is_details_form_valid,
            details_form_class,
            details_form,
            can_submit,
        )
        blocks: list[Block] = [
            *intro_blocks,
            DividerBlock(),
            *set_impacts_blocks,
            *choose_response_type_blocks,
            *select_incident_type_blocks,
            *set_details_blocks,
            *done_review_blocks,
        ]
        return View(
            type="modal",
            title="Create an incident"[:24],
            submit="Create the incident"[:24] if can_submit else None,
            callback_id=self.callback_id,
            blocks=blocks,
            clear_on_close=False,
            close=None,
        )

    @staticmethod
    def get_intro_blocks() -> list[Block]:
        blocks: list[Block] = [
            SectionBlock(
                text="Hello and thanks for reporting a new incident! :beetle:\n\nPlease report as much information as you can!"
            )
        ]

        recent_critical_incidents: int = Incident.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        if recent_critical_incidents > 0:
            blocks.append(
                OpenModal.warning_recent_critical_incidents(recent_critical_incidents)
            )

        return blocks

    @staticmethod
    def get_set_impact_blocks(
        open_incident_context: OpeningData, *, impact_form_done: bool
    ) -> list[Block]:
        from firefighter.slack.views.modals.opening.select_impact import (  # noqa: PLC0415
            SelectImpactModal,
        )

        return [
            SectionBlock(
                text=f"{'✅' if impact_form_done else '📝'} First, define the incident impacts and priority.",
                accessory=ButtonElement(
                    text="Edit impacts" if impact_form_done else "Set impacts",
                    action_id=SelectImpactModal.push_action,
                    value=json.dumps(open_incident_context, cls=SlackFormJSONEncoder),
                ),
            ),
        ]

    @staticmethod
    def warning_recent_critical_incidents(count: int) -> SectionBlock:
        return SectionBlock(
            text=ngettext(
                "> 🚨 A critical incident has been created in the past hour. Please check it to avoid duplicate incidents.",
                "> 🚨 %(count)d critical incidents have been created in the past hour. Please check them to avoid duplicate incidents.",
                count,
            )
            % {"count": count},
            accessory=ButtonElement(
                text="Check incidents",
                action_id=CheckCurrentIncidentsModal.push_action,
            ),
        )

    @staticmethod
    def get_set_details_blocks(
        open_incident_context: OpeningData,
        *,
        details_form_done: bool,
        details_form_modal_class: type[SetIncidentDetails[Any]] | None,
    ) -> list[Block]:
        if details_form_modal_class is None:
            return []
        return [
            SectionBlock(
                text=f"{'✅' if details_form_done else '📝'} Finally, add incident details",
                accessory=ButtonElement(
                    text="Edit details" if details_form_done else "Set details",
                    action_id=details_form_modal_class.push_action,
                    value=json.dumps(open_incident_context, cls=SlackFormJSONEncoder),
                ),
            ),
        ]

    @staticmethod
    def get_select_incident_type_blocks(
        open_incident_context: OpeningData,
        incident_type_value: str | None,
    ) -> list[Block]:
        response_type = open_incident_context.get("response_type")
        if (
            response_type is None
            or response_type not in INCIDENT_TYPES
            or len(INCIDENT_TYPES[response_type]) == 1
        ):
            return []
        options = [
            Option(value=incident_type, label=incident_type_data["label"])
            for incident_type, incident_type_data in INCIDENT_TYPES[
                response_type
            ].items()
        ]
        initial_option = next(
            filter(lambda x: x.value == incident_type_value, options), None
        )
        return [
            SectionBlock(
                text=("✅" if incident_type_value else "📝")
                + _("Then, select the type of issue / affected users"),
                accessory=StaticSelectElement(
                    placeholder=_("Set type"),
                    action_id="set_type",
                    options=options,
                    initial_option=initial_option,
                ),
            ),
        ]

    @staticmethod
    def get_done_review_blocks(
        open_incident_context: OpeningData,
        user: User,
        details_form_done: bool,  # noqa: FBT001
        details_form_class: type[CreateIncidentFormBase] | None,
        details_form: CreateIncidentFormBase | None,
        can_submit: bool,  # noqa: FBT001
    ) -> list[Block]:
        if not can_submit:
            return []
        done_review_blocks: list[Block] = [
            DividerBlock(),
            SectionBlock(
                text=":tada: Almost done! Click the button below to create the incident."
            ),
        ]

        if open_incident_context.get("response_type") == "critical":
            slack_msg = None
            if details_form_done and details_form_class and details_form:
                incident = Incident(
                    status=IncidentStatus.OPEN,  # type: ignore
                    created_by=user,
                    **details_form.cleaned_data,
                )
                users_list: set[User] = {*incident.build_invite_list(), user}
                slack_msg = f"> :slack: A dedicated Slack channel will be created, and around {len(users_list)} responders will be invited to help.\n"

            if slack_msg is None:
                slack_msg = "> :slack: A dedicated Slack channel will be created, and responders will be invited to help.\n"
            text = f"> :firefighter_incident: This will trigger a critical incident response.\n{slack_msg}> :jira_new: An associated Jira ticket will also be created."
            if not is_during_office_hours(timezone.now()):
                text += "\n> :pagerduty: If you need it, you'll be able to escalate the incident to our 24/7 on-call response teams."
        else:
            text = "> :raid_logo: This will trigger a normal incident response.\n> :jira_new: A Jira ticket will be created."
        done_review_blocks += [SectionBlock(text=text)]

        return done_review_blocks

    @staticmethod
    def _check_impact_form(open_incident_context: OpeningData) -> bool:
        done = bool(
            open_incident_context and open_incident_context.get("impact_form_data")
        )
        if not done:
            return False
        form = SelectImpactForm(open_incident_context.get("impact_form_data"))
        if not form.is_valid():
            return False
        return True

    def _check_details_form(
        self,
        open_incident_context: OpeningData,
        incident_type_value: str | None,
    ) -> tuple[
        bool,
        type[CreateIncidentFormBase] | None,
        type[SetIncidentDetails[Any]] | None,
        CreateIncidentFormBase | None,
    ]:
        details_form_done = False
        details_form_class = None
        details_form = None

        details_form_modal_class = self.get_details_modal_form_class(
            open_incident_context, incident_type_value
        )

        if (
            open_incident_context.get("details_form_data")
            and "details_form_data" in open_incident_context
            and open_incident_context["details_form_data"] is not None
        ):
            (
                details_form_done,
                details_form_class,
                details_form,
            ) = self._validate_details_form(
                details_form_modal_class, open_incident_context["details_form_data"]
            )

        return (
            details_form_done,
            details_form_class,
            details_form_modal_class,
            details_form,
        )

    @staticmethod
    def _validate_details_form(
        details_form_modal_class: type[SetIncidentDetails[Any]] | None,
        details_form_data: dict[str, Any],
    ) -> tuple[
        bool, type[CreateIncidentFormBase] | None, CreateIncidentFormBase | None
    ]:
        if not details_form_modal_class:
            return False, None, None

        details_form_class: type[
            CreateIncidentFormBase
        ] = details_form_modal_class.form_class

        if not details_form_class:
            return False, None, None

        details_form: CreateIncidentFormBase = details_form_class(details_form_data)
        is_valid = details_form.is_valid()

        return is_valid, details_form_class, details_form

    @staticmethod
    def _build_response_type_blocks(open_incident_context: OpeningData) -> list[Block]:
        selected_response_type = open_incident_context.get("response_type")
        if selected_response_type not in {"critical", "normal"}:
            return []

        response_types: list[ResponseType] = cast(
            list[ResponseType], INCIDENT_TYPES.keys()
        )
        elements: list[ButtonElement] = []

        for response_type in response_types:
            is_selected = (
                open_incident_context.get("response_type") == response_type
                or len(INCIDENT_TYPES) == 1
            )
            style: str | None = "primary" if is_selected else None
            icon = (
                ":firefighter_incident:"
                if response_type == "critical"
                else ":raid_logo:"
            )
            text = (
                f"{response_type.capitalize()} incident {icon if is_selected else ''}"
            )
            button = ButtonElement(
                text=text,
                action_id=f"incident_open_set_res_type_{response_type}",
                value=json.dumps(open_incident_context, cls=SlackFormJSONEncoder),
                style=style,
            )
            elements.append(button)

        blocks: list[Block] = [ActionsBlock(elements=elements)]
        if impact_form_data := open_incident_context.get("impact_form_data"):
            impact_form = SelectImpactForm(impact_form_data)
            if impact_form.is_valid():
                priority: Priority = Priority.objects.get(
                    value=impact_form.suggest_priority_from_impact()
                )
                blocks.append(
                    ContextBlock(
                        elements=[
                            MarkdownTextObject(
                                text=f"> {priority.emoji} Selected priority: {priority}"
                                + (
                                    (
                                        "\n> Critical incidents are for *emergency* only"
                                        + (
                                            f"<{SLACK_SEVERITY_HELP_GUIDE_URL}|learn more>"
                                            if SLACK_SEVERITY_HELP_GUIDE_URL
                                            else "" + "."
                                        )
                                    )
                                    if selected_response_type == "critical"
                                    else ""
                                )
                            )
                        ]
                    ),
                )

                if (
                    priority.recommended_response_type
                    and priority.recommended_response_type != selected_response_type
                ):
                    blocks.append(
                        ContextBlock(
                            elements=[
                                MarkdownTextObject(
                                    text=f"> :warning: The current priority ({priority}) is usually handled with a {priority.recommended_response_type} response type."
                                )
                            ]
                        )
                    )

        return blocks

    @staticmethod
    def get_details_modal_form_class(
        open_incident_context: OpeningData,
        incident_type_value: str | None,
    ) -> type[SetIncidentDetails[Any]] | None:
        """Get the details modal form class based on the incident type.

        Returns None if no incident type is selected.
        """
        response_type = open_incident_context.get("response_type")
        if response_type is None:
            return None
        incident_types = INCIDENT_TYPES.get(response_type)
        if incident_types and len(incident_types) == 1:
            return incident_types[next(iter(incident_types.keys()))].get("slack_form")
        if incident_types and incident_type_value is not None:
            return incident_types[incident_type_value].get("slack_form")
        logger.debug(
            f"No incident type found for {open_incident_context}. No fallback."
        )
        return None

    def handle_modal_fn(  # type: ignore
        self,
        ack: Ack,
        body: dict[str, Any],
        user: User,
    ):
        """Handle response from /incident open modal."""
        data: OpeningData = json.loads(body["view"]["private_metadata"])

        details_form_data_raw = data.get("details_form_data", {})

        incident_type_value: str | None = data.get("incident_type", None)

        details_form_modal_class = self.get_details_modal_form_class(
            data, incident_type_value
        )
        if details_form_modal_class:
            details_form_class: type[
                CreateIncidentFormBase
            ] = details_form_modal_class.form_class
            if details_form_class:
                details_form: CreateIncidentFormBase = details_form_class(
                    details_form_data_raw
                )
                details_form.is_valid()
                ack()
                try:
                    if hasattr(details_form, "trigger_incident_workflow") and callable(
                        details_form.trigger_incident_workflow
                    ):
                        details_form.trigger_incident_workflow(
                            creator=user,
                            impacts_data=data.get("impact_form_data") or {},
                        )
                except:  # noqa: E722
                    logger.exception("Error triggering incident workflow")
                    # XXX warn the user via DM!

    @app.action("incident_open_set_res_type_normal")
    @app.action("incident_open_set_res_type_critical")
    @staticmethod
    def handle_set_incident_response_type_action(
        ack: Ack, body: dict[str, Any]
    ) -> None:
        action_name: str = body.get("actions", [{}])[0].get("action_id", "")
        action_name = action_name.replace("incident_open_set_res_type_", "")
        opening_data = cast(
            OpeningData, json.loads(body.get("actions", [{}])[0].get("value", {})) or {}
        )

        OpenModal._update_incident_modal(
            action_name, "response_type", ack, body, opening_data
        )

    @app.action("set_type")
    @staticmethod
    def handle_set_incident_type_action(ack: Ack, body: dict[str, Any]) -> None:
        incident_type_value: str = (
            body.get("actions", [{}])[0].get("selected_option", {}).get("value", "")
        )
        opening_data = json.loads(body.get("view", {}).get("private_metadata", "{}"))
        OpenModal._update_incident_modal(
            incident_type_value, "incident_type", ack, body, opening_data
        )

    @classmethod
    def _update_incident_modal(
        cls,
        action_value: str,
        metadata_key: Literal["incident_type", "response_type"],
        ack: Ack,
        body: dict[str, Any],
        opening_data: OpeningData,
    ) -> None:
        data: OpeningData = {**opening_data, metadata_key: action_value}  # type: ignore
        user = get_user_from_context(body)
        view = cls().build_modal_fn(open_incident_context=data, user=user)

        view.private_metadata = json.dumps(data, cls=SlackFormJSONEncoder)
        ack()
        update_modal(view=view, body=body)


modal_open = OpenModal()
