"""Timeline review checkpoint shown before an incident moves to Post-mortem.

This does not change how the timeline is recorded today - every status
change still comes from the normal Update Status modal. It only inserts a
confirmation step right before the Post-mortem transition, showing the
timeline as already recorded and letting a human accept it (the transition
then proceeds normally, and the confirmed timeline is pushed into the
incident's Jira post-mortem "Timeline" field, if any) or reject it (the
transition is cancelled, and a correction message - same pattern as the Key
Events message - lets the human edit the recorded times directly, each
change saving immediately).

Accepting is not the end of it: a timeline is often found wrong after the
fact. The correction message can be reopened from the accepted review message
and from the Update menu, and re-checking it then re-syncs the post-mortem and
the metrics instead of transitioning a second time.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from slack_sdk.models.blocks import Block, ContextBlock, HeaderBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import ActionsBlock
from slack_sdk.models.views import View

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.timeline import IncidentTimelineForm
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import incident_key_events_updated
from firefighter.incidents.timeline import (
    EXPECTED_ORDER,
    find_timeline_issues,
    get_canonical_steps,
)
from firefighter.slack.messages.base import SlackMessageStrategy, SlackMessageSurface
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_incident_context import get_user_from_context
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import MessageForm
from firefighter.slack.views.modals.base_modal.modal_utils import update_modal
from firefighter.slack.views.modals.timeline_preview import (
    timeline_chain,
    timeline_preview_blocks,
    timeline_span,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.base_modal.form_utils import SlackForm

logger = logging.getLogger(__name__)
app = SlackApp()

# The Update Status modal's own open action, reused rather than re-registered:
# a button carrying it and the incident id opens that modal from any message
# (see `slack_incident_context.get_incident_from_button_value`). Referenced by
# value, not by import - `update_status` imports this module through
# `modals.utils`, so importing it back would close the cycle.
UPDATE_STATUS_ACTION_ID = "open_modal_incident_update_status"

ACCEPT_ACTION_ID = "review_timeline_accept"
REJECT_ACTION_ID = "review_timeline_reject"
RECHECK_ACTION_ID = "review_timeline_recheck"
CORRECT_ACTION_ID = "review_timeline_correct"
OPEN_TIMELINE_CORRECTION_ACTION_ID = "open_timeline_correction"

# Fields carried over from the Update Status submission so they aren't lost
# while the human reviews the timeline (mirrors utils._build_carry_over_from_form).
# "status" is deliberately excluded: the accept handler always sets it to
# IncidentStatus.POST_MORTEM explicitly.
_CARRY_OVER_FIELDS: tuple[str, ...] = (
    "priority_id",
    "incident_category_id",
    "message",
    "title",
    "description",
)


def build_carry_over_payload(incident: Incident, update_kwargs: dict[str, Any]) -> str:
    """Serialize the incident id and carried-over form fields into a button value."""
    payload: dict[str, Any] = {"incident_id": incident.id}
    for field in _CARRY_OVER_FIELDS:
        if field in update_kwargs:
            value = update_kwargs[field]
            payload[field] = str(value) if field.endswith("_id") else value
    return json.dumps(payload)


def _parse_action_payload(body: dict[str, Any]) -> dict[str, Any] | None:
    actions = body.get("actions") or []
    if not actions:
        return None
    raw_value = actions[0].get("value")
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError):
        logger.exception("Could not parse review timeline action payload: %s", raw_value)
        return None


def _get_incident(body: dict[str, Any], incident_id: Any) -> Incident | None:
    try:
        return Incident.objects.get(pk=incident_id)
    except (Incident.DoesNotExist, ValueError, TypeError):
        respond(body, text=":x: Incident not found.")
        return None


def can_correct_timeline(incident: Incident) -> bool:
    """Whether the timeline of this incident is still open to corrections.

    A closed incident is out: its metrics are consolidated and its post-mortem
    is out of FireFighter's hands, so a late edit would silently disagree with
    what has already been reported. Those corrections go through the admin,
    deliberately.
    """
    return incident.status < IncidentStatus.CLOSED


class SlackMessageReviewTimeline(SlackMessageSurface):
    id = "ff_incident_timeline_review"
    # Each new pending review posts fresh and removes the previous review
    # message for this incident (REPLACE) - not an edit of a previous,
    # possibly long-buried one (e.g. a prior rejection, with a lot of channel
    # activity since). Resolving a review (Accept/Reject) still updates that
    # specific message in place, but does so by explicitly targeting the
    # clicked message - see `_resolved_message_strategy_args` - rather than
    # relying on this class-level strategy.
    strategy: SlackMessageStrategy = SlackMessageStrategy.REPLACE

    def __init__(
        self,
        incident: Incident,
        carry_over_payload: str | None = None,
        resolution: str | None = None,
    ) -> None:
        """`resolution` is None while pending, or "accepted"/"rejected"/"corrected"."""
        self.incident = incident
        self.carry_over_payload = carry_over_payload
        self.resolution = resolution
        super().__init__()

    def get_text(self) -> str:
        return f"Timeline review before Post-mortem for {self.incident}."

    def get_blocks(self) -> list[Block]:
        steps = get_canonical_steps(self.incident)
        issues = find_timeline_issues(steps)
        flagged = {issue.label for issue in issues}
        single_day, span = timeline_span(steps)

        heading = ":stopwatch: Timeline Review"
        if span:
            heading = f"{heading} — {span}"

        # Same chain as every other surface (Key Events, correction message):
        # one line, the seven key events, unrecorded ones as a dash.
        blocks: list[Block] = [
            HeaderBlock(text=heading),
            SectionBlock(
                text=timeline_chain(steps, single_day=single_day, flagged=flagged)
            ),
        ]

        if issues:
            details = "\n".join(f"> • {issue.message}" for issue in issues)
            blocks.append(
                SectionBlock(
                    text=(
                        f":warning: *{len(issues)} issue"
                        f"{'s' if len(issues) > 1 else ''} to fix before "
                        f"continuing*\n{details}"
                    )
                )
            )
        elif self.resolution is None:
            blocks.append(
                SectionBlock(
                    text=":white_check_mark: *No inconsistency detected* — order and recorded times are consistent."
                )
            )

        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text="Expected order: " + " → ".join(EXPECTED_ORDER)
                        + "   ·   ↻ = reopen cycles"
                    )
                ]
            )
        )

        if self.resolution in {"accepted", "corrected"}:
            blocks.extend(self._resolved_blocks())
        elif self.resolution == "rejected":
            blocks.append(
                SectionBlock(
                    text=(
                        ":x: Timeline not accepted — the Post-mortem transition was cancelled.\n"
                        "Correct the recorded times in the message below, then update the "
                        "status to *Post-mortem* again."
                    )
                )
            )
        else:
            # Accept is withheld while the timeline is inconsistent: a wrong
            # timeline drives the post-mortem and the incident metrics. Slack
            # cannot disable a button, so it is simply not rendered - the accept
            # handler re-checks as well, since an older message stays clickable.
            actions = []
            if not issues:
                actions.append(
                    ButtonElement(
                        text="Looks correct — continue to Post-mortem",
                        style="primary",
                        action_id=ACCEPT_ACTION_ID,
                        value=self.carry_over_payload,
                    )
                )
            actions.append(
                ButtonElement(
                    text="Not accurate — let me fix it",
                    action_id=REJECT_ACTION_ID,
                    value=self.carry_over_payload,
                )
            )
            blocks.append(ActionsBlock(elements=actions))
        return blocks

    def _resolved_blocks(self) -> list[Block]:
        """Outcome of the review, plus the way back into the correction form.

        A timeline is regularly found wrong after it was accepted - that is the
        whole reason this button exists. It stays on the message for as long as
        corrections are allowed, so the reviewer does not have to remember which
        surface to reopen.
        """
        text = (
            ":white_check_mark: Timeline accepted — incident moved to Post-mortem."
            if self.resolution == "accepted"
            else ":white_check_mark: Timeline corrected — post-mortem and metrics re-synced."
        )
        blocks: list[Block] = [SectionBlock(text=text)]
        if can_correct_timeline(self.incident):
            blocks.append(
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="Something's off — correct the timeline",
                            action_id=CORRECT_ACTION_ID,
                            value=build_carry_over_payload(self.incident, {}),
                        ),
                        _update_incident_button(self.incident),
                    ]
                )
            )
        return blocks


def _update_incident_button(incident: Incident) -> ButtonElement:
    """Open Update Status straight from the timeline.

    Correcting a timeline and moving the incident on are two halves of the same
    moment, and the timeline messages are where that moment happens. Without
    this the reviewer has to scroll the channel back to the declaration message
    or type the command again.
    """
    return ButtonElement(
        text="Update incident",
        value=str(incident.id),
        action_id=UPDATE_STATUS_ACTION_ID,
    )


def _resolved_message_strategy_args(body: dict[str, Any]) -> dict[str, Any] | None:
    """Target the exact message that was clicked, from the interaction payload.

    "Last message of this type" (the fallback when this returns None) is
    usually correct, since REPLACE removes the previous review message when
    a new one is posted - but explicit targeting is still more direct and
    avoids relying on that being true. Returns None if the payload doesn't
    carry the expected fields (e.g. in tests), in which case the caller
    falls back to the ff_type lookup.
    """
    message_ts = (body.get("container") or {}).get("message_ts")
    channel_id = (body.get("channel") or {}).get("id")
    if message_ts is None or channel_id is None:
        return None
    return {"ts": message_ts, "channel_id": channel_id}


def post_timeline_correction(incident: Incident) -> None:
    """Post a fresh correction message in the incident channel.

    REPLACE, not UPDATE: a new correction cycle removes the stale message from
    a previous one rather than editing it in place, wherever it was buried.
    Editing a single field within the same cycle
    (`TimelineCorrection.update_with_form`) still updates in place.
    """
    incident.conversation.send_message_and_save(
        SlackMessageTimelineCorrection(incident),
        strategy=SlackMessageStrategy.REPLACE,
    )


@app.action(ACCEPT_ACTION_ID)
def handle_review_timeline_accept(ack: Ack, body: dict[str, Any]) -> None:
    ack()
    _resolve_timeline(body, update_in_place=True)


@app.action(RECHECK_ACTION_ID)
def handle_review_timeline_recheck(ack: Ack, body: dict[str, Any]) -> None:
    """Re-run the checks from the correction message, then transition or re-sync.

    Saves a round trip through the Update Status modal once the times are fixed.
    The transition it applies carries the status only: the message and any
    priority or category change from the original submission cannot be threaded
    across the correction step, so nothing pretends to carry them.
    """
    ack()
    _resolve_timeline(body, update_in_place=False)


@app.action(CORRECT_ACTION_ID)
def handle_review_timeline_correct(ack: Ack, body: dict[str, Any]) -> None:
    """Reopen the correction form from a resolved review message."""
    ack()
    payload = _parse_action_payload(body)
    if payload is None:
        return
    incident = _get_incident(body, payload.get("incident_id"))
    if incident is None:
        return
    if not can_correct_timeline(incident):
        respond(
            body,
            text=":x: This incident is closed — its timeline can no longer be corrected here.",
        )
        return
    post_timeline_correction(incident)


@app.action(OPEN_TIMELINE_CORRECTION_ACTION_ID)
def handle_open_timeline_correction(ack: Ack, body: dict[str, Any]) -> None:
    """Open the correction form from the Update menu, outside any review cycle.

    The form is a channel message, not a modal (see `TimelineCorrection`), so the
    modal that was clicked from reports where the message went instead of
    hosting the form itself.
    """
    ack()
    actions = body.get("actions") or []
    incident = _get_incident(body, actions[0].get("value") if actions else None)
    if incident is None:
        return
    if not can_correct_timeline(incident):
        respond(
            body,
            text=":x: This incident is closed — its timeline can no longer be corrected here.",
        )
        return

    post_timeline_correction(incident)
    update_modal(
        body=body,
        view=View(
            type="modal",
            title=f"Incident #{incident.id}"[:24],
            blocks=[
                SectionBlock(
                    text=(
                        ":stopwatch: A *Correct the timeline* message was posted in "
                        f"<#{incident.conversation.channel_id}>.\n"
                        "Each time you edit there saves immediately, and the preview "
                        "at the top of the message updates with it."
                    )
                )
            ],
        ),
    )


def _resolve_timeline(body: dict[str, Any], *, update_in_place: bool) -> None:
    """Finish a review: transition to Post-mortem, or re-sync an already-made one.

    The same buttons serve both a first review (the incident has yet to reach
    Post-mortem) and a late correction (it is already there). Re-running the
    transition in the second case would record a second Post-mortem
    `IncidentUpdate` and shift the timeline it is meant to fix, so the status
    change is applied once and only once.
    """
    payload = _parse_action_payload(body)
    if payload is None:
        return
    incident_id = payload.pop("incident_id")
    incident = _get_incident(body, incident_id)
    if incident is None:
        return
    if not can_correct_timeline(incident):
        respond(
            body,
            text=":x: This incident is closed — its timeline can no longer be corrected here.",
        )
        return

    # Re-check server-side: the button is not rendered when the timeline is
    # inconsistent, but an older review message left in the channel stays
    # clickable, so the gate cannot live in the rendering alone.
    issues = find_timeline_issues(get_canonical_steps(incident))
    if issues:
        respond(
            body,
            text=(
                ":warning: The timeline still has "
                f"{len(issues)} issue{'s' if len(issues) > 1 else ''} to fix: "
                + "; ".join(issue.message for issue in issues)
            ),
        )
        return

    already_reviewed = incident.status >= IncidentStatus.POST_MORTEM
    user = get_user_from_context(body)
    # Flush the edits made in the correction form now that the reviewer is done:
    # this refreshes the Key Events form message (it shows the same milestones)
    # and re-syncs the Jira timeline, once instead of once per keystroke.
    incident_key_events_updated.send_robust(__name__, incident=incident)
    if already_reviewed:
        # Nothing to transition to: the carried-over fields, if any, belong to
        # an Update Status submission that was applied at the original review.
        incident.compute_metrics()
    else:
        incident.create_incident_update(
            created_by=user, status=IncidentStatus.POST_MORTEM, **payload
        )
    _push_confirmed_timeline_to_jira(incident)
    # Accept edits the review message it was clicked from; the re-check button
    # lives on the correction message, so it posts the outcome as a new message
    # rather than overwriting a form the reviewer may still be reading.
    strategy_args = _resolved_message_strategy_args(body) if update_in_place else None
    incident.conversation.send_message_and_save(
        SlackMessageReviewTimeline(
            incident, resolution="corrected" if already_reviewed else "accepted"
        ),
        strategy=SlackMessageStrategy.UPDATE if update_in_place else SlackMessageStrategy.APPEND,
        strategy_args=strategy_args,
    )


def _push_confirmed_timeline_to_jira(incident: Incident) -> None:
    """Push the just-accepted timeline into the incident's Jira post-mortem, if any.

    Guarded by an app-installed check, not just the ENABLE_JIRA_POSTMORTEM
    setting: `firefighter.jira_app` is only added to INSTALLED_APPS when Jira
    is enabled (see settings/components/jira_app.py), so importing its models
    when the app isn't installed would be unsafe. This keeps `slack` free of
    a hard dependency on `jira_app` being present.
    """
    from django.apps import apps

    if not apps.is_installed("firefighter.jira_app"):
        return

    from firefighter.jira_app.signals import sync_timeline_to_jira_postmortem

    sync_timeline_to_jira_postmortem(incident)


# Matches this form's field names (milestone_started, status_<uuid>, ...) so
# touching any of its datetimepickers routes here - mirrors key_event_message's
# MILESTONE_ID_REGEX, kept distinct from it to avoid any ambiguity between the
# two forms' action ids.
TIMELINE_CORRECTION_ID_REGEX = re.compile(r"^(milestone|status)_.*$")


class TimelineCorrection(MessageForm[IncidentTimelineForm]):
    """Correction message, same pattern as Key Events: edit a field, it saves immediately.

    Chosen over a modal because a modal's fixed height makes many fields
    (2 milestones + one per status reached) cramped and scroll-heavy; a
    channel message doesn't have that constraint and matches a surface
    users are already familiar with.
    """

    form_class = IncidentTimelineForm
    callback_id = TIMELINE_CORRECTION_ID_REGEX
    callback_action = True

    def build_modal_fn(self, incident: Incident) -> list[Block]:
        slack_form: SlackForm[IncidentTimelineForm] = self.get_form_class()(
            incident=incident
        )
        return self.get_blocks_from_form(slack_form.form)

    def get_blocks_from_form(self, form: IncidentTimelineForm) -> list[Block]:
        incident = form.incident
        # The preview leads, so the effect of an edit is visible right where it
        # is made - the fields below are the same seven key events, in order.
        blocks: list[Block] = timeline_preview_blocks(
            incident, title=":stopwatch: Correct the timeline"
        )
        slack_form: SlackForm[IncidentTimelineForm] = self.get_form_class()
        slack_form.form = form
        blocks += slack_form.slack_blocks()

        # Deliberately not an "accept" button: it re-runs the checks, and only
        # then transitions (first review) or re-syncs (correction after the
        # fact). Its payload is the incident id alone - the original Update
        # Status submission (its message, any priority or category change)
        # cannot be threaded across the correction step, and this way nothing
        # pretends to carry it.
        already_reviewed = incident.status >= IncidentStatus.POST_MORTEM
        blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text=(
                            "Re-check & re-sync the post-mortem"
                            if already_reviewed
                            else "Re-check timeline & continue to Post-mortem"
                        ),
                        style="primary",
                        action_id=RECHECK_ACTION_ID,
                        value=build_carry_over_payload(incident, {}),
                    ),
                    _update_incident_button(incident),
                ]
            )
        )
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=(
                            "Each edit saves immediately; the post-mortem and the "
                            "metrics are re-synced shortly after. Re-check to sync now."
                            if already_reviewed
                            else "Re-checking applies the status change only. To also "
                            "post an update message, run *Update Status* → "
                            "*Post-mortem* instead."
                        )
                    )
                ]
            )
        )
        return blocks

    def handle_modal_fn(  # type: ignore[override]
        self, ack: Ack, body: dict[str, Any], user: User, incident: Incident
    ) -> None:
        slack_form = self.handle_form_errors(
            ack, body, forms_kwargs={"incident": incident, "user": user}
        )
        form = slack_form.form if slack_form else None
        if form is None:
            logger.warning("Form is None, skipping save")
            return
        self.form = form
        if len(form.errors) > 0:
            self.update_with_form()
            return
        self.form.save()

        # Metrics are cheap and local, so they stay in sync on every edit.
        incident.compute_metrics()

        # `incident_key_events_updated` is deliberately NOT sent from here. This
        # method runs on every single field edit, and the signal fans out to a
        # Jira round trip plus a refresh of the Key Events form message - which
        # shows the same milestones, so Slack marks it "(edited)" and resurfaces
        # it on every keystroke. The sync is deferred and debounced instead, so
        # a burst of corrections costs one round trip; the re-check button also
        # forces it immediately, from `_resolve_timeline`.
        #
        # Imported here: `slack.tasks` pulls in the whole task package, which
        # imports the message surfaces back - a module-level import would close
        # the cycle at startup.
        from firefighter.slack.tasks.sync_timeline import schedule_timeline_sync

        schedule_timeline_sync(incident)

        # Only the correction message itself is refreshed here, to echo the
        # value that was just saved - and the preview above the fields with it.
        self.update_with_form()

    def update_with_form(self) -> None:
        self.form.incident.conversation.send_message_and_save(
            SlackMessageTimelineCorrection(self.form.incident)
        )


timeline_correction_surface = TimelineCorrection()


class SlackMessageTimelineCorrection(SlackMessageSurface):
    id = "ff_incident_timeline_correction"
    strategy: SlackMessageStrategy = SlackMessageStrategy.UPDATE

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        super().__init__()

    def get_blocks(self) -> list[Block]:
        return TimelineCorrection().build_modal_fn(self.incident)

    def get_text(self) -> str:
        return f"Correct the timeline for {self.incident}."


@app.action(REJECT_ACTION_ID)
def handle_review_timeline_reject(ack: Ack, body: dict[str, Any]) -> None:
    ack()
    payload = _parse_action_payload(body)
    if payload is None:
        return
    incident = _get_incident(body, payload.get("incident_id"))
    if incident is None:
        return

    incident.conversation.send_message_and_save(
        SlackMessageReviewTimeline(incident, resolution="rejected"),
        strategy=SlackMessageStrategy.UPDATE,
        strategy_args=_resolved_message_strategy_args(body),
    )
    post_timeline_correction(incident)
