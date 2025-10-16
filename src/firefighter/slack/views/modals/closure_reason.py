from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks.basic_components import MarkdownTextObject, Option
from slack_sdk.models.blocks.block_elements import (
    PlainTextInputElement,
    StaticSelectElement,
)
from slack_sdk.models.blocks.blocks import (
    Block,
    ContextBlock,
    DividerBlock,
    InputBlock,
    SectionBlock,
)
from slack_sdk.models.views import View

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.slack.slack_templating import slack_block_footer, slack_block_separator
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, User

logger = logging.getLogger(__name__)


class ClosureReasonModal(IncidentSelectableModalMixin, SlackModal):
    """Modal for closing an incident with a mandatory reason from early statuses."""

    open_action: str = "closure_reason_incident"
    open_shortcut = "closure_reason_incident"
    callback_id: str = "incident_closure_reason"

    def build_modal_fn(
        self, body: dict[str, Any], incident: Incident, **kwargs: Any  # noqa: ARG002
    ) -> View:
        """Build the closure reason modal."""
        # Build closure reason options (exclude RESOLVED)
        closure_options = [
            Option(
                value=choice[0],
                label=choice[1],
            )
            for choice in ClosureReason.choices
            if choice[0] != ClosureReason.RESOLVED
        ]

        blocks: list[Block] = [
            SectionBlock(
                text=f"*Closure Reason Required for Incident #{incident.id}*\n_{incident.title}_"
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f"⚠️ This incident is currently in *{incident.status.label}* status.\nA closure reason is required to close incidents from this status."
                    )
                ]
            ),
            DividerBlock(),
            InputBlock(
                block_id="closure_reason",
                label="Closure Reason",
                element=StaticSelectElement(
                    action_id="select_closure_reason",
                    options=closure_options,
                    placeholder="Select a reason...",
                ),
                hint="Why is this incident being closed directly?",
            ),
            InputBlock(
                block_id="closure_reference",
                label="Reference (optional)",
                element=PlainTextInputElement(
                    action_id="input_closure_reference",
                    placeholder="e.g., #1234 or https://...",
                    max_length=100,
                ),
                hint="Related incident ID or external reference",
                optional=True,
            ),
            InputBlock(
                block_id="closure_message",
                label="Closure Message",
                element=PlainTextInputElement(
                    action_id="input_closure_message",
                    multiline=True,
                    placeholder="Brief explanation of why this incident is being closed...",
                ),
                hint="This message will be added to the incident timeline",
            ),
            slack_block_separator(),
            slack_block_footer(),
        ]

        return View(
            type="modal",
            title=f"Close #{incident.id}"[:24],
            submit="Close Incident",
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    def handle_modal_fn(  # type: ignore[override]
        self, ack: Ack, body: dict[str, Any], incident: Incident, user: User
    ) -> bool | None:
        """Handle the closure reason modal submission."""
        # Clear ALL modals in the stack (not just this one)
        # This ensures the underlying "Update Status" modal is also closed
        ack(response_action="clear")

        # Extract form values
        state_values = body["view"]["state"]["values"]
        closure_reason = state_values["closure_reason"]["select_closure_reason"][
            "selected_option"
        ]["value"]
        closure_reference = (
            state_values["closure_reference"]["input_closure_reference"].get("value", "")
            or ""
        )
        message = state_values["closure_message"]["input_closure_message"]["value"]

        try:
            # Update incident with closure fields
            incident.closure_reason = closure_reason
            incident.closure_reference = closure_reference
            incident.save(update_fields=["closure_reason", "closure_reference"])

            # Create incident update with closure
            incident.create_incident_update(
                created_by=user,
                status=IncidentStatus.CLOSED,
                message=message,
                event_type="closure_reason",
            )

        except Exception:
            logger.exception(
                "Error closing incident #%s with reason", incident.id
            )
            respond(
                body=body,
                text=f"❌ Failed to close incident #{incident.id}",
            )
            return False
        else:
            # Send confirmation message
            try:
                respond(
                    body=body,
                    text=(
                        f"✅ Incident #{incident.id} has been closed.\n"
                        f"*Reason:* {ClosureReason(closure_reason).label}\n"
                        f"*Message:* {message}"
                        + (f"\n*Reference:* {closure_reference}" if closure_reference else "")
                    ),
                )
            except SlackApiError as e:
                if e.response.get("error") == "messages_tab_disabled":
                    logger.warning(
                        "Cannot send DM to user %s - messages tab disabled",
                        user.email,
                    )
                else:
                    # Re-raise for other Slack API errors
                    raise

            logger.info(
                "Incident #%s closed with reason by %s: %s",
                incident.id,
                user.email,
                closure_reason,
            )
            return True

    def get_select_modal_title(self) -> str:
        return "Close with Reason"

    def get_select_title(self) -> str:
        return "Select an incident to close with a specific reason"


modal_closure_reason = ClosureReasonModal()
