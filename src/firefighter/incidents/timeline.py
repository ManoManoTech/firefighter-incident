"""The incident timeline: its canonical steps, and the checks they must satisfy.

Kept out of the Slack layer because three surfaces render the same seven steps
(the Post-mortem review checkpoint, the Key Events message and the timeline
correction message) and the Jira post-mortem is built from the same data. The
rendering differs; the definition of "the timeline" must not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from django.utils.timezone import localtime, now

from firefighter.incidents.enums import IncidentStatus

if TYPE_CHECKING:
    import datetime

    from firefighter.incidents.models.incident import Incident

# Which occurrence of a status is the definitive one when a reopen makes it
# repeat: investigation *started* at its first occurrence, while the mitigation
# that actually held is the last one. Shared by every surface so they all show -
# and edit - the same timestamp.
DEFINITIVE_OCCURRENCE: dict[IncidentStatus, str] = {
    IncidentStatus.INVESTIGATING: "first",
    IncidentStatus.MITIGATING: "last",
    IncidentStatus.MITIGATED: "last",
}
DEFAULT_OCCURRENCE = "last"

# (event_type, display label) for the milestones collected via the Key Events
# form (see fixtures/incidents/milestone_type.json). They aren't guaranteed to
# be filled in, since that form is user-editable and can be skipped.
MILESTONE_EVENT_TYPES: tuple[tuple[str, str], ...] = (
    ("started", "Started"),
    ("detected", "Detected"),
)

# The seven key events of an incident, in the order they are expected to happen.
# This interleaving of milestones and statuses lives nowhere else: MilestoneType
# has no `order` field and IncidentStatus only orders the statuses among
# themselves. Single source of truth for every timeline preview, for the
# displayed legend and for the consistency checks.
#
# label, emoji, source key, and whether a missing time is an error. Only the
# milestones are mandatory (MilestoneType.required): a status that never
# happened - an incident going straight from Declared to Mitigated, say - is
# not a mistake and must not be reported as one.
EXPECTED_STEPS: tuple[tuple[str, str, str | IncidentStatus, bool], ...] = (
    ("Started", ":firecracker:", "started", True),
    ("Detected", ":eyes:", "detected", True),
    ("Declared", ":loudspeaker:", IncidentStatus.OPEN, False),
    ("Investigating", ":mag:", IncidentStatus.INVESTIGATING, False),
    ("Mitigating", ":wrench:", IncidentStatus.MITIGATING, False),
    ("Mitigated", ":white_check_mark:", IncidentStatus.MITIGATED, False),
    ("Post-mortem", ":memo:", IncidentStatus.POST_MORTEM, False),
)

EXPECTED_ORDER: tuple[str, ...] = tuple(label for label, *_ in EXPECTED_STEPS)

# What each status means, in the same voice as `MilestoneType.summary` ("when
# the first issues arose"), which supplies the milestones' own definitions. The
# editable surfaces show these under their field: a key event is only recorded
# consistently if everyone reads it the same way.
STATUS_HINTS: dict[IncidentStatus, str] = {
    IncidentStatus.INVESTIGATING: "When the team started looking into it.",
    IncidentStatus.MITIGATING: (
        "When a fix, a rollback or a workaround started being applied."
    ),
    IncidentStatus.MITIGATED: "When the actions applied stopped the impact.",
}


class TimelineEntry(NamedTuple):
    label: str
    event_ts: datetime.datetime | None
    """None if this milestone was never recorded via the Key Events form."""


class TimelineStep(NamedTuple):
    label: str
    emoji: str
    event_ts: datetime.datetime | None
    occurrences: int
    required: bool


class TimelineIssue(NamedTuple):
    label: str
    message: str


def get_status_timeline(
    incident: Incident,
) -> list[tuple[IncidentStatus, datetime.datetime]]:
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

    Unlike `get_canonical_steps`, this keeps every occurrence: it is the full
    audit trail, not the seven-step summary.
    """
    milestone_updates = milestone_timestamps(incident)
    milestones = sorted(
        (
            TimelineEntry(label=label, event_ts=milestone_updates.get(event_type))
            for event_type, label in MILESTONE_EVENT_TYPES
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


def get_canonical_steps(incident: Incident) -> list[TimelineStep]:
    """One step per `EXPECTED_STEPS` entry, collapsing reopen cycles.

    A reopened incident goes through Investigating/Mitigating/Mitigated more than
    once. Listing every occurrence makes the sequence impossible to check against
    the expected order and buries the definitive times, so each step keeps a
    single timestamp and carries its occurrence count instead.
    """
    milestone_updates = milestone_timestamps(incident)
    status_occurrences: dict[IncidentStatus, list[datetime.datetime]] = {}
    for status, event_ts in get_status_timeline(incident):
        status_occurrences.setdefault(status, []).append(event_ts)

    steps: list[TimelineStep] = []
    for label, emoji, source, required in EXPECTED_STEPS:
        step_ts: datetime.datetime | None
        if isinstance(source, str):
            step_ts = milestone_updates.get(source)
            count = 1 if step_ts is not None else 0
        else:
            stamps = sorted(status_occurrences.get(source) or [])
            count = len(stamps)
            which = DEFINITIVE_OCCURRENCE.get(source, DEFAULT_OCCURRENCE)
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
            issues.append(TimelineIssue(label, f"*{label}* is in the future"))
        if previous is not None and event_ts < previous[1]:
            issues.append(
                TimelineIssue(
                    label,
                    f"*{label}* ({localtime(event_ts).strftime('%H:%M:%S')}) is "
                    f"{format_delta(previous[1] - event_ts)} before *{previous[0]}* "
                    f"({localtime(previous[1]).strftime('%H:%M:%S')})",
                )
            )
        previous = (label, event_ts)
    return issues


def format_delta(delta: datetime.timedelta) -> str:
    """Human-readable duration, keeping the two most significant units."""
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


def milestone_timestamps(incident: Incident) -> dict[str, datetime.datetime]:
    """The recorded `event_ts` of each milestone, newest row winning per type.

    Explicit ordering: without it `Meta.ordering` ("-event_ts") applies and
    `dict()` would keep the oldest row per type, so two surfaces reading the
    same milestone would disagree.
    """
    rows = (
        incident.incidentupdate_set.filter(
            event_type__in=[event_type for event_type, _ in MILESTONE_EVENT_TYPES]
        )
        .order_by("event_ts")
        .values_list("event_type", "event_ts")
    )
    # `event_type` is nullable on the model - the filter above rules those rows
    # out, but the column's type does not say so.
    return {
        event_type: event_ts for event_type, event_ts in rows if event_type is not None
    }
