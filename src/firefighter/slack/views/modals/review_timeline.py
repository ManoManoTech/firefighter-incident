"""Timeline review checkpoint shown before an incident moves to Post-mortem.

This does not change how the timeline is recorded today — every status
change still comes from the normal Update Status modal. It only inserts a
confirmation step right before the Post-mortem transition, showing the
timeline as already recorded and letting a human accept it (the transition
then proceeds normally, and the confirmed timeline is pushed into the
incident's Jira post-mortem "Timeline" field, if any) or reject it (the
transition is cancelled, and a correction message - same pattern as the Key
Events message - lets the human edit the recorded times directly, each
change saving immediately).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple

from django.utils.timezone import localtime, now
from slack_sdk.models.blocks import Block, ContextBlock, HeaderBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import ActionsBlock

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.timeline_correction import (
    DEFINITIVE_OCCURRENCE,
    TimelineCorrectionForm,
)
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import incident_key_events_updated
from firefighter.slack.messages.base import SlackMessageStrategy, SlackMessageSurface
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_incident_context import get_user_from_context
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import MessageForm

if TYPE_CHECKING:
    import datetime

    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.user import User
    from firefighter.slack.views.modals.base_modal.form_utils import SlackForm

logger = logging.getLogger(__name__)
app = SlackApp()

ACCEPT_ACTION_ID = "review_timeline_accept"
REJECT_ACTION_ID = "review_timeline_reject"
RECHECK_ACTION_ID = "review_timeline_recheck"

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


def get_status_timeline(incident: Incident) -> list[tuple[IncidentStatus, datetime.datetime]]:
    """Every status transition, in chronological order, including reopen cycles.

    The declaration `OPEN` row always anchors to `incident.created_at` (the
    incident's true start), never to whichever `OPEN` row happens to be
    latest - so it's added explicitly rather than trusted from the DB row.
    An incident can legitimately go back to `OPEN` later (a real reopen);
    that row has a different `event_ts` than `created_at` and is kept, so it
    shows up as its own entry rather than being silently dropped. Every
    other status contributes one entry per row - a status revisited after a
    reopen (MITIGATED -> INVESTIGATING/MITIGATING) shows every visit,
    matching the full audit trail rendered in the Jira post-mortem timeline.
    """
    timeline: list[tuple[IncidentStatus, datetime.datetime]] = [
        (IncidentStatus.OPEN, incident.created_at)
    ]
    updates = incident.incidentupdate_set.filter(_status__isnull=False).order_by(
        "event_ts"
    )
    for update in updates:
        status = update.status
        if status is None:
            continue
        if status == IncidentStatus.OPEN and update.event_ts == incident.created_at:
            continue  # already represented by the anchor above
        timeline.append((status, update.event_ts))
    return sorted(timeline, key=lambda item: item[1])


class TimelineEntry(NamedTuple):
    label: str
    event_ts: datetime.datetime | None
    """None if this milestone was never recorded via the Key Events form."""


# (event_type, display label), in the order they should appear before the
# status timeline - both are collected via the Key Events form (see
# fixtures/incidents/milestone_type.json) but aren't guaranteed to be filled
# in, since that form is user-editable and can be skipped.
# The expected chronological order of an incident, spanning both milestones and
# status transitions. This interleaving lives nowhere else: MilestoneType has no
# `order` field and IncidentStatus only orders the statuses among themselves.
# Single source of truth for the displayed legend and the consistency checks.
# label, emoji, source key, and which occurrence to keep when a status repeats
# after a reopen: investigation *started* at its first occurrence, while the
# mitigation that actually held is the last one - and that is the one the
# post-mortem timeline must show.
# label, emoji, source, and whether a missing time is an error. Only the
# milestones are mandatory (MilestoneType.required): a status that never
# happened - an incident going straight from Declared to Mitigated, say - is
# not a mistake and must not be reported as one.
_EXPECTED_STEPS: tuple[tuple[str, str, str | IncidentStatus, bool], ...] = (
    ("Started", ":firecracker:", "started", True),
    ("Detected", ":eyes:", "detected", True),
    ("Declared", ":loudspeaker:", IncidentStatus.OPEN, False),
    ("Investigating", ":mag:", IncidentStatus.INVESTIGATING, False),
    ("Mitigating", ":wrench:", IncidentStatus.MITIGATING, False),
    ("Mitigated", ":white_check_mark:", IncidentStatus.MITIGATED, False),
    ("Post-mortem", ":memo:", IncidentStatus.POST_MORTEM, False),
)

_EXPECTED_ORDER: tuple[str, ...] = tuple(label for label, *_ in _EXPECTED_STEPS)

_MILESTONE_EVENT_TYPES: tuple[tuple[str, str], ...] = (
    ("started", "Started"),
    ("detected", "Detected"),
)


def get_incident_timeline(incident: Incident) -> list[TimelineEntry]:
    """Started/Detected milestones (if recorded), followed by the status timeline.

    Milestones missing a recorded `event_ts` are still included, with
    `event_ts=None`, so the reviewer notices the gap rather than the
    milestone silently disappearing from the list. The milestone group
    itself is sorted chronologically (Detected can legitimately be recorded
    before Started, e.g. an automated alert fires before the actual start is
    pinpointed) - unrecorded milestones sort last within the group, since
    there's no time to place them by. The group as a whole always leads the
    status timeline, since milestones routinely predate the incident being
    declared in FireFighter. Only the first `OPEN` entry (the one anchored to
    `incident.created_at`) is relabeled "Declared" - a later `OPEN` entry is
    a genuine reopen and keeps reading "Open".
    """
    milestone_updates = dict(
        incident.incidentupdate_set.filter(
            event_type__in=[event_type for event_type, _ in _MILESTONE_EVENT_TYPES]
        )
        .order_by("event_ts")
        .values_list("event_type", "event_ts")
    )
    milestones = sorted(
        (
            TimelineEntry(label=label, event_ts=milestone_updates.get(event_type))
            for event_type, label in _MILESTONE_EVENT_TYPES
        ),
        key=lambda entry: (entry.event_ts is None, entry.event_ts),
    )
    status_entries = []
    declared_shown = False
    for status, event_ts in get_status_timeline(incident):
        if status == IncidentStatus.OPEN and not declared_shown:
            label = "Declared"
            declared_shown = True
        else:
            label = status.label
        status_entries.append(TimelineEntry(label=label, event_ts=event_ts))
    return [*milestones, *status_entries]


class TimelineIssue(NamedTuple):
    label: str
    message: str


def _format_delta(delta: datetime.timedelta) -> str:
    seconds = int(abs(delta).total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = [
        f"{value}{unit}"
        for value, unit in ((days, "d"), (hours, "h"), (minutes, "m"), (seconds, "s"))
        if value
    ]
    return " ".join(parts[:2]) if parts else "0s"


class TimelineStep(NamedTuple):
    label: str
    emoji: str
    event_ts: datetime.datetime | None
    occurrences: int
    required: bool


def get_canonical_steps(incident: Incident) -> list[TimelineStep]:
    """One step per `_EXPECTED_STEPS` entry, collapsing reopen cycles.

    A reopened incident goes through Investigating/Mitigating/Mitigated more than
    once. Listing every occurrence makes the sequence impossible to check against
    the expected order and buries the definitive times, so each step keeps a
    single timestamp and carries its occurrence count instead.
    """
    milestone_updates = dict(
        incident.incidentupdate_set.filter(
            event_type__in=[event_type for event_type, _ in _MILESTONE_EVENT_TYPES]
        )
        .order_by("event_ts")
        .values_list("event_type", "event_ts")
    )
    status_occurrences: dict[IncidentStatus, list[datetime.datetime]] = {}
    for status, event_ts in get_status_timeline(incident):
        status_occurrences.setdefault(status, []).append(event_ts)

    steps: list[TimelineStep] = []
    for label, emoji, source, required in _EXPECTED_STEPS:
        step_ts: datetime.datetime | None
        if isinstance(source, str):
            step_ts = milestone_updates.get(source)
            count = 1 if step_ts is not None else 0
        else:
            stamps = sorted(status_occurrences.get(source) or [])
            count = len(stamps)
            which = DEFINITIVE_OCCURRENCE.get(source, "last")
            step_ts = (stamps[-1] if which == "last" else stamps[0]) if stamps else None
        steps.append(TimelineStep(label, emoji, step_ts, count, required))
    return steps


def find_timeline_issues(steps: list[TimelineStep]) -> list[TimelineIssue]:
    """Checks the recorded steps against the expected chronology.

    Reports steps that break the order, required steps with no recorded time,
    and times in the future - the three ways a hand-typed timeline goes wrong.
    """
    issues: list[TimelineIssue] = []
    right_now = now()
    previous: tuple[str, datetime.datetime] | None = None
    for step in steps:
        label = step.label
        event_ts = step.event_ts
        if event_ts is None:
            if step.required:
                issues.append(
                    TimelineIssue(
                        label, f"*{label}* is required and has no recorded time"
                    )
                )
            continue
        if event_ts > right_now:
            issues.append(
                TimelineIssue(label, f"*{label}* is in the future")
            )
        if previous is not None and event_ts < previous[1]:
            issues.append(
                TimelineIssue(
                    label,
                    f"*{label}* ({localtime(event_ts).strftime('%H:%M:%S')}) is "
                    f"{_format_delta(previous[1] - event_ts)} before *{previous[0]}* "
                    f"({localtime(previous[1]).strftime('%H:%M:%S')})",
                )
            )
        previous = (label, event_ts)
    return issues


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
        """`resolution` is None while pending, or "accepted"/"rejected" once resolved."""
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

        recorded = sorted(
            localtime(step.event_ts) for step in steps if step.event_ts is not None
        )
        dates = {ts.date() for ts in recorded}
        # Incidents can span several days, so the date is never dropped: a single
        # day goes in the heading and the rows carry times only, otherwise the
        # heading carries the range and every row carries its own day.
        single_day = len(dates) == 1
        heading = ":stopwatch: Timeline Review"
        if recorded:
            first, last = recorded[0].date(), recorded[-1].date()
            if single_day:
                span = first.strftime("%d %b %Y")
            elif (first.year, first.month) == (last.year, last.month):
                span = f"{first.day} → {last.strftime('%d %b %Y')}"
            elif first.year == last.year:
                span = f"{first.strftime('%d %b')} → {last.strftime('%d %b %Y')}"
            else:
                span = f"{first.strftime('%d %b %Y')} → {last.strftime('%d %b %Y')}"
            heading = f"{heading} — {span} ({recorded[0].strftime('%Z')})"

        blocks: list[Block] = [HeaderBlock(text=heading)]

        # Horizontal chain: reads as a timeline at a glance and wraps on its own
        # in Slack. Times are minute-precision here to keep the chain short - the
        # exact seconds are in the issue list below and in the correction form.
        chain = []
        for step in steps:
            if step.event_ts is None and not step.required:
                continue
            if step.event_ts is None:
                stamp = "_not recorded_"
            else:
                local = localtime(step.event_ts)
                stamp = local.strftime("%H:%M" if single_day else "%d/%m %H:%M")
            marks = " :warning:" if step.label in flagged else ""
            reopened = f" ↻{step.occurrences - 1}" if step.occurrences > 1 else ""
            chain.append(f"{step.emoji} *{step.label}* {stamp}{marks}{reopened}")
        blocks.append(SectionBlock(text="  ➜  ".join(chain)))

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
                        text="Expected order: " + " → ".join(_EXPECTED_ORDER)
                        + "   ·   ↻ = reopen cycles"
                    )
                ]
            )
        )

        if self.resolution == "accepted":
            blocks.append(
                SectionBlock(
                    text=":white_check_mark: Timeline accepted — incident moved to Post-mortem."
                )
            )
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


@app.action(ACCEPT_ACTION_ID)
def handle_review_timeline_accept(ack: Ack, body: dict[str, Any]) -> None:
    ack()
    _resolve_timeline_and_transition(body, update_in_place=True)


@app.action(RECHECK_ACTION_ID)
def handle_review_timeline_recheck(ack: Ack, body: dict[str, Any]) -> None:
    """Re-run the checks from the correction message and transition if clean.

    Saves a round trip through the Update Status modal once the times are fixed.
    The transition it applies carries the status only: the message and any
    priority or category change from the original submission cannot be threaded
    across the correction step, so nothing pretends to carry them.
    """
    ack()
    _resolve_timeline_and_transition(body, update_in_place=False)


def _resolve_timeline_and_transition(
    body: dict[str, Any], *, update_in_place: bool
) -> None:
    payload = _parse_action_payload(body)
    if payload is None:
        return
    incident_id = payload.pop("incident_id")
    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        respond(body, text=":x: Incident not found.")
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

    user = get_user_from_context(body)
    # Flush the edits made in the correction form now that the reviewer is done:
    # this refreshes the Key Events form message (it shows the same milestones)
    # and re-syncs the Jira timeline, once instead of once per keystroke.
    incident_key_events_updated.send_robust(__name__, incident=incident)
    incident.create_incident_update(
        created_by=user, status=IncidentStatus.POST_MORTEM, **payload
    )
    _push_confirmed_timeline_to_jira(incident)
    # Accept edits the review message it was clicked from; the re-check button
    # lives on the correction message, so it posts the outcome as a new message
    # rather than overwriting a form the reviewer may still be reading.
    strategy_args = _resolved_message_strategy_args(body) if update_in_place else None
    incident.conversation.send_message_and_save(
        SlackMessageReviewTimeline(incident, resolution="accepted"),
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


class TimelineCorrection(MessageForm[TimelineCorrectionForm]):
    """Correction message, same pattern as Key Events: edit a field, it saves immediately.

    Chosen over a modal because a modal's fixed height makes many fields
    (2 milestones + one per status reached) cramped and scroll-heavy; a
    channel message doesn't have that constraint and matches a surface
    users are already familiar with.
    """

    form_class = TimelineCorrectionForm
    callback_id = TIMELINE_CORRECTION_ID_REGEX
    callback_action = True

    def build_modal_fn(self, incident: Incident) -> list[Block]:
        slack_form: SlackForm[TimelineCorrectionForm] = self.get_form_class()(
            incident=incident
        )
        return self.get_blocks_from_form(slack_form.form)

    def get_blocks_from_form(self, form: TimelineCorrectionForm) -> list[Block]:
        blocks: list[Block] = [
            HeaderBlock(text=":stopwatch: Correct the timeline"),
            SectionBlock(
                text="Edit any time below - each change saves immediately."
            ),
        ]
        slack_form: SlackForm[TimelineCorrectionForm] = self.get_form_class()
        slack_form.form = form
        blocks += slack_form.slack_blocks()
        # Deliberately not an "accept" button: it re-runs the checks and only
        # transitions if they pass. Its payload is the incident id alone - the
        # original Update Status submission (its message, any priority or
        # category change) cannot be threaded across the correction step, and
        # this way nothing pretends to carry it.
        blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="Re-check timeline & continue to Post-mortem",
                        style="primary",
                        action_id=RECHECK_ACTION_ID,
                        value=build_carry_over_payload(form.incident, {}),
                    ),
                ]
            )
        )
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=(
                            "Re-checking applies the status change only. To also "
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

        # `incident_key_events_updated` is deliberately NOT sent here. This
        # method runs on every single field edit, and the signal fans out to a
        # Jira round trip plus a refresh of the Key Events form message - which
        # shows the same started/detected values, so Slack marks it "(edited)"
        # and resurfaces it on every keystroke. Both are done once the reviewer
        # is finished, from `_resolve_timeline_and_transition`, which keeps the
        # two surfaces consistent without the noise (and without ~2 Jira calls
        # per edited field).
        #
        # Only the correction message itself is refreshed here, to echo the
        # value that was just saved.
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
    incident_id = payload["incident_id"]
    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        respond(body, text=":x: Incident not found.")
        return

    incident.conversation.send_message_and_save(
        SlackMessageReviewTimeline(incident, resolution="rejected"),
        strategy=SlackMessageStrategy.UPDATE,
        strategy_args=_resolved_message_strategy_args(body),
    )
    # REPLACE here (not the class default UPDATE) so a new reject cycle
    # removes a stale correction message from a previous one, rather than
    # editing it in place. Editing a single field within the same cycle
    # (TimelineCorrection.update_with_form) still uses UPDATE - cheap,
    # in-place, no need to delete/repost on every field change.
    incident.conversation.send_message_and_save(
        SlackMessageTimelineCorrection(incident),
        strategy=SlackMessageStrategy.REPLACE,
    )
