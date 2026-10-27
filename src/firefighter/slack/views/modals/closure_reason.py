from __future__ import annotations

import json
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

from firefighter.incidents.enums import (
    OFFERED_CLOSURE_REASONS,
    ClosureReason,
    IncidentOrigin,
    IncidentStatus,
    status_for_closure_reason,
)
from firefighter.incidents.models.partner import Partner
from firefighter.incidents.origin import apply_origin, resolve_partner
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

CLOSURE_CHOICE_LABELS: dict[ClosureReason, str] = {
    ClosureReason.RESOLVED: "Yes, a real incident, already resolved",
    ClosureReason.DUPLICATE: "No: duplicate of another incident",
    ClosureReason.FALSE_POSITIVE: "No: false alarm, no actual issue",
    ClosureReason.SUPERSEDED: "No: superseded by another incident",
    ClosureReason.CANCELLED: "No: cancelled, no longer relevant",
}
"""The question asked first: was it a real incident? Rejection reasons all say no."""

SLACK_MAX_OPTIONS = 100


def origin_blocks(incident: Incident) -> list[Block]:
    """Origin of a real incident: internal by default, or a partner."""
    origin = IncidentOrigin(incident.origin)
    blocks: list[Block] = [
        InputBlock(
            block_id="closure_origin",
            label="Origin of the incident (real incident only)",
            element=StaticSelectElement(
                action_id="select_closure_origin",
                options=[Option(value=o.value, label=o.label) for o in IncidentOrigin],
                initial_option=Option(value=origin.value, label=origin.label),
            ),
            hint="Partner: the incident comes from a third party we depend on (search, CDN, payment...).",
        )
    ]
    partners = list(Partner.objects.filter(is_active=True).order_by("name")[:SLACK_MAX_OPTIONS])
    if partners:
        partner_options = [Option(value=str(p.id), label=p.name) for p in partners]
        current = next((o for o in partner_options if incident.partner_id and o.value == str(incident.partner_id)), None)
        blocks.append(
            InputBlock(
                block_id="closure_partner",
                label="Partner",
                element=StaticSelectElement(
                    action_id="select_closure_partner",
                    options=partner_options,
                    initial_option=current,
                    placeholder="Select a partner...",
                ),
                optional=True,
            )
        )
    blocks.append(
        InputBlock(
            block_id="closure_new_partner",
            label="Partner not in the list? Add it",
            element=PlainTextInputElement(
                action_id="input_closure_new_partner", max_length=128
            ),
            optional=True,
        )
    )
    return blocks


def _read_origin(
    state_values: dict[str, Any],
) -> tuple[IncidentOrigin, str | None, str | None]:
    """Origin, selected partner id and typed partner name submitted with the modal."""
    origin = IncidentOrigin(
        _selected_value(state_values, "closure_origin", "select_closure_origin")
        or IncidentOrigin.INTERNAL
    )
    partner_id = _selected_value(state_values, "closure_partner", "select_closure_partner")
    new_partner = _selected_value(
        state_values, "closure_new_partner", "input_closure_new_partner"
    )
    return origin, partner_id, new_partner


def _apply_origin(
    incident: Incident,
    origin: IncidentOrigin,
    partner_id: str | None,
    new_partner: str | None,
    user: User,
) -> None:
    partner = resolve_partner(
        Partner.objects.filter(id=partner_id).first() if partner_id else None,
        new_partner,
        user=user,
        incident=incident,
    )
    apply_origin(incident, origin, partner, user=user)


def _selected_value(state_values: dict[str, Any], block_id: str, action_id: str) -> str | None:
    action = state_values.get(block_id, {}).get(action_id) or {}
    if "selected_option" in action:
        return (action.get("selected_option") or {}).get("value")
    return (action.get("value") or "").strip() or None


class ClosureReasonModal(IncidentSelectableModalMixin, SlackModal):
    """Modal for closing an incident with a mandatory reason from early statuses."""

    open_action: str = "closure_reason_incident"
    open_shortcut = "closure_reason_incident"
    callback_id: str = "incident_closure_reason"

    def build_modal_fn(
        self,
        body: dict[str, Any],  # noqa: ARG002
        incident: Incident,
        carry_over: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> View:
        """Build the closure reason modal.

        `carry_over` lets upstream callers (Update Status modal) pass form
        changes that should be applied along with the closure (e.g. a priority
        change submitted in the same step). Values are serialized into
        `private_metadata` so they survive the round-trip to Slack.
        """
        blocks: list[Block] = [
            SectionBlock(
                text=f"*Close incident #{incident.id}*\n_{incident.title}_"
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f"This incident is currently in *{incident.status.label}* status. "
                        "Tell whether it was a real incident: a real one is *Closed*, "
                        "any other is *Rejected* and kept out of the incident statistics."
                    )
                ]
            ),
            DividerBlock(),
            InputBlock(
                block_id="closure_reason",
                label="Was this a real incident?",
                element=StaticSelectElement(
                    action_id="select_closure_reason",
                    options=[
                        Option(value=reason.value, label=CLOSURE_CHOICE_LABELS[reason])
                        for reason in OFFERED_CLOSURE_REASONS
                    ],
                    placeholder="Select...",
                ),
            ),
            *origin_blocks(incident),
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
            private_metadata=_build_private_metadata(incident.id, carry_over),
            blocks=blocks,
        )

    def handle_modal_fn(  # type: ignore[override]
        self, ack: Ack, body: dict[str, Any], incident: Incident, user: User
    ) -> bool | None:
        """Handle the closure reason modal submission."""
        # Extract form values up-front so validation can account for the submitted reason
        state_values = body["view"]["state"]["values"]
        closure_reason = state_values["closure_reason"]["select_closure_reason"][
            "selected_option"
        ]["value"]
        closure_reference = (
            state_values["closure_reference"]["input_closure_reference"].get(
                "value", ""
            )
            or ""
        )
        message = state_values["closure_message"]["input_closure_message"]["value"]
        carry_over = _extract_carry_over(body)
        target_status = status_for_closure_reason(closure_reason)
        origin, partner_id, new_partner = _read_origin(state_values)
        # The origin only describes a real incident: a rejected one has none to give
        if (
            target_status == IncidentStatus.CLOSED
            and origin == IncidentOrigin.PARTNER
            and not (partner_id or new_partner)
        ):
            ack(
                response_action="errors",
                errors={
                    "closure_new_partner": "Pick the partner, or add it if it is not in the list."
                },
            )
            return False

        # For early closure (OPEN/INVESTIGATING), we bypass normal workflow checks
        # For normal closure (MITIGATED/POST_MORTEM), we must validate key events
        current_status = incident.status
        is_early_closure = current_status.value in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}

        if not is_early_closure:
            # Normal closure path - validate that incident can be closed
            can_close, reasons = incident.can_be_closed
            if not can_close:
                # Build error message from reasons
                error_messages = [reason[1] for reason in reasons]
                error_text = "\n".join([f"• {msg}" for msg in error_messages])
                ack(
                    response_action="errors",
                    errors={
                        "closure_message": f"Cannot close this incident:\n{error_text}"
                    }
                )
                return False
        else:
            # Early closure path - validate with the submitted closure reason
            # Temporarily inject the submitted closure_reason so early-closure bypass applies
            original_closure_reason = incident.closure_reason
            incident.closure_reason = closure_reason
            try:
                can_close, reasons = incident.can_be_closed
            finally:
                incident.closure_reason = original_closure_reason
            if not can_close:
                # Build error message from reasons
                error_messages = [reason[1] for reason in reasons]
                error_text = "\n".join([f"• {msg}" for msg in error_messages])
                ack(
                    response_action="errors",
                    errors={
                        "closure_message": f"Cannot close this incident:\n{error_text}"
                    },
                )
                return False

        # Clear ALL modals in the stack (not just this one)
        # This ensures the underlying "Update Status" modal is also closed
        ack(response_action="clear")

        try:
            # Update incident with closure fields
            incident.closure_reason = closure_reason
            incident.closure_reference = closure_reference
            incident.save(update_fields=["closure_reason", "closure_reference"])

            if target_status == IncidentStatus.CLOSED:
                _apply_origin(incident, origin, partner_id, new_partner, user)

            # Create incident update with closure
            incident.create_incident_update(
                created_by=user,
                status=target_status,
                message=message,
                event_type="closure_reason",
                **carry_over,
            )

        except Exception:
            logger.exception("Error closing incident #%s with reason", incident.id)
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
                        f"✅ Incident #{incident.id} has been {target_status.label.lower()}.\n"
                        f"*Reason:* {ClosureReason(closure_reason).label}\n"
                        f"*Message:* {message}"
                        + (
                            f"\n*Reference:* {closure_reference}"
                            if closure_reference
                            else ""
                        )
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


# Carry-over kwargs the closure reason modal will re-apply when closing the
# incident. Whitelisted to keep deserialization tight and avoid passing unknown
# kwargs to ``create_incident_update``.
_ALLOWED_CARRY_OVER_KEYS: frozenset[str] = frozenset(
    {"priority_id", "incident_category_id"}
)


def _build_private_metadata(
    incident_id: int, carry_over: dict[str, Any] | None
) -> str:
    """Serialize the closure modal's private metadata.

    Without carry-over we keep the legacy plain-int format for backwards
    compatibility. When carry-over fields are present we switch to a JSON
    object — the incident resolver supports both shapes.
    """
    sanitized = {
        k: v
        for k, v in (carry_over or {}).items()
        if k in _ALLOWED_CARRY_OVER_KEYS and v is not None
    }
    if not sanitized:
        return str(incident_id)
    return json.dumps({"incident_id": incident_id, "carry_over": sanitized})


def _extract_carry_over(body: dict[str, Any]) -> dict[str, Any]:
    """Read carry-over kwargs back from the submitted view's private_metadata."""
    raw = body.get("view", {}).get("private_metadata")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    carry_over = parsed.get("carry_over")
    if not isinstance(carry_over, dict):
        return {}
    return {k: v for k, v in carry_over.items() if k in _ALLOWED_CARRY_OVER_KEYS}


modal_closure_reason = ClosureReasonModal()
