# Timeline review and corrections

The seven key events of an incident - Started, Detected, Declared, Investigating,
Mitigating, Mitigated, Post-mortem - drive the post-mortem and the incident
metrics. They are recorded by two different mechanisms (the Key Events form for
the milestones, the status transitions for the rest), so they are also reviewed,
and correctable, as one.

## The seven key events

`firefighter.incidents.timeline` is the single definition of the timeline:
`EXPECTED_STEPS` interleaves milestones and statuses in their expected order,
`get_canonical_steps()` resolves one timestamp per step (collapsing reopen cycles
onto the occurrence that counts) and `find_timeline_issues()` reports the three
ways a hand-typed timeline goes wrong: a required step with no time, a time in
the future, a step before the one preceding it.

Every Slack surface renders those steps through
`slack.views.modals.timeline_preview`, as one compact line. Unrecorded steps show
a dash rather than disappearing, so the line keeps its shape as the timeline
fills in.

## The review checkpoint

Moving a post-mortem-worthy incident to *Post-mortem* through **Update Status**
does not transition it straight away. The review message shows the timeline as
recorded and offers:

- **Looks correct — continue to Post-mortem**, only rendered when the timeline
  passes the checks (the handler re-checks server-side: an older message left in
  the channel stays clickable). The incident transitions, and the confirmed
  timeline is pushed into the Jira post-mortem's Timeline field.
- **Not accurate — let me fix it**, which cancels the transition and posts the
  correction message.

## Editing the timeline

`incidents.forms.timeline.IncidentTimelineForm` is the single editable form, and
both Slack surfaces render it: the **Key Events** message (posted at Mitigated,
and the one that carries the *Close incident* button) and the **timeline
correction** message. Same fields, same order, same preview on top - only the
footer differs.

It covers every key event that can be corrected:

- the milestones flagged `user_editable` (Started, Detected, Recovered in the
  default fixtures). `Declared` is not one of them: it is the incident's
  declaration time, anchored to `created_at`.
- the statuses between the declaration and the post-mortem (Investigating,
  Mitigating, Mitigated). A status the incident went through edits its
  definitive occurrence in place and is **required** - a transition that happened
  has to keep some time. A status it never went through is offered **empty and
  optional**: filling it records that step (an incident that jumped straight from
  Declared to Mitigated can be completed after the fact). Recording a step this
  way does not move the incident: its current status lives on the incident
  itself, not on these rows.

`OPEN` and `POST_MORTEM` are shown in the preview but never offered as fields:
the declaration is the incident's creation time, and the Post-mortem stamp is
written by the transition itself, at the instant it happens - the very
transition this checkpoint gates.

Every field carries the definition of its key event underneath, as Slack's hint:
the milestones' come from `MilestoneType.summary` (minus the Markdown and the
repeated name, neither of which Slack renders in a label), the statuses' from
`timeline.STATUS_HINTS`.

Each surface owns its action ids through `field_prefix` (`key_event_` for the Key
Events message, none for the correction one), so an edit routes back to the
message it was made in.

Each field saves on its own, immediately.

The correction message can be opened from three places:

| Entry point | When |
| --- | --- |
| Rejecting the review | The incident has yet to reach Post-mortem |
| **Something's off — correct the timeline**, on the resolved review message | The review was already accepted |
| **Fix timeline**, in the Update menu | The incident is in Post-mortem |

Re-checking runs the consistency checks again, then does one of two things,
depending on where the incident already is:

- **before Post-mortem**: applies the status transition (status only - the
  message, priority or category of the original Update Status submission cannot
  be threaded across the correction step),
- **already in Post-mortem**: changes no status at all, and only re-syncs the
  post-mortem and the metrics. Transitioning a second time would add a Post-mortem
  row to the very timeline being corrected.

Once the incident is **closed**, its metrics and post-mortem are consolidated:
the buttons are no longer offered and the handlers refuse. Late corrections go
through the Django admin (`IncidentUpdate.event_ts`, then the *Compute metrics*
action on the incident).

## Syncing back

A correction is not worth a Jira round trip per keystroke, so
`slack.tasks.sync_timeline` batches them - for both surfaces: the first edit of a
window arms a deferred task, the following ones ride along, and the sync runs once. It
recomputes the metrics and sends `incident_key_events_updated`, which refreshes
the Key Events message and pushes the timeline to the Jira post-mortem.

The window is `FF_TIMELINE_SYNC_DEBOUNCE_SECONDS` (30 s by default). Re-checking
forces the sync immediately, without waiting for it.
