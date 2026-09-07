"""One small, shared rendering of the seven key events, for every Slack surface.

The Key Events message, the timeline correction message and the Post-mortem
review checkpoint all describe the same timeline. They used to describe it
differently (or not at all), so a reviewer had to open a third surface to see
what their edit had just done. They now share this preview: one line, always the
seven canonical steps, unrecorded ones shown as a dash rather than hidden - so
the shape of the line stays the same as it fills in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.timezone import localtime
from slack_sdk.models.blocks import Block, ContextBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject

from firefighter.incidents.timeline import (
    find_timeline_issues,
    get_canonical_steps,
)

if TYPE_CHECKING:
    from collections.abc import Collection

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.timeline import TimelineStep

NOT_RECORDED = "—"


def timeline_span(steps: Collection[TimelineStep]) -> tuple[bool, str | None]:
    """Whether every recorded step falls on one day, and the span to display.

    Incidents can run over several days, so the date is never dropped: on a
    single day it goes in the heading and the steps carry times only, otherwise
    each step carries its own day.
    """
    recorded = sorted(
        localtime(step.event_ts) for step in steps if step.event_ts is not None
    )
    if not recorded:
        return True, None

    first, last = recorded[0].date(), recorded[-1].date()
    single_day = len({ts.date() for ts in recorded}) == 1
    if single_day:
        span = first.strftime("%d %b %Y")
    elif (first.year, first.month) == (last.year, last.month):
        span = f"{first.day} → {last.strftime('%d %b %Y')}"
    elif first.year == last.year:
        span = f"{first.strftime('%d %b')} → {last.strftime('%d %b %Y')}"
    else:
        span = f"{first.strftime('%d %b %Y')} → {last.strftime('%d %b %Y')}"
    return single_day, f"{span} ({recorded[0].strftime('%Z')})"


def timeline_chain(
    steps: Collection[TimelineStep],
    *,
    single_day: bool,
    flagged: Collection[str] = (),
    with_labels: bool = True,
) -> str:
    """The seven steps as one wrapping line: emoji, label, time.

    Minute precision keeps the line short - exact seconds live in the issue
    messages and in the correction fields. `with_labels=False` drops the step
    names for the smallest possible rendering, for surfaces that already spell
    the steps out underneath (the correction form's own fields).
    """
    chain = []
    for step in steps:
        if step.event_ts is None:
            stamp = NOT_RECORDED
        else:
            local = localtime(step.event_ts)
            stamp = local.strftime("%H:%M" if single_day else "%d/%m %H:%M")
        label = f" *{step.label}*" if with_labels else ""
        marks = " :warning:" if step.label in flagged else ""
        reopened = f" ↻{step.occurrences - 1}" if step.occurrences > 1 else ""
        chain.append(f"{step.emoji}{label} {stamp}{marks}{reopened}")
    return "  ➜  ".join(chain)


def timeline_preview_blocks(
    incident: Incident, *, title: str = ":stopwatch: Timeline"
) -> list[Block]:
    """Compact preview: one line for the timeline, one line if it has issues.

    Deliberately two blocks at most. It sits on top of forms that people are
    filling in, and every field they edit re-renders the message it lives in -
    a preview that grows with the incident would push the fields off screen.
    """
    steps = get_canonical_steps(incident)
    issues = find_timeline_issues(steps)
    single_day, span = timeline_span(steps)
    heading = f"*{title}*" + (f"  ·  _{span}_" if span else "")

    blocks: list[Block] = [
        SectionBlock(
            text=(
                f"{heading}\n"
                f"{timeline_chain(steps, single_day=single_day, flagged={issue.label for issue in issues})}"
            )
        )
    ]
    if issues:
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f":warning: {len(issues)} issue{'s' if len(issues) > 1 else ''}: "
                        + " · ".join(issue.message for issue in issues)
                    )
                ]
            )
        )
    return blocks
