# ADR-0001: Rejected status and incident origin

**Status**: Accepted
**Date**: 2026-10-27

## Context

Every incident used to end in the same `CLOSED` status, whether it was a real incident fixed after mitigation or something that was never one: a duplicate, a false alarm, an incident superseded by another, a cancelled one. The early-closure modal already asked for a *closure reason*, and `Incident.closure_reason` stored it, but nothing read it outside Slack: the API, the reports, the metrics and the Jira ticket all treated a duplicate exactly like a real outage. Incident counts and time-to-X metrics were skewed, and the Jira ticket of a duplicate was resolved as *Done* (or, when the sync fell back to the workflow's `Reject` transition without its required fields, not updated at all).

Separately, many real incidents are caused by a third party the platform depends on (search, CDN, payment provider...). There was no way to record it: the only option was the `external` closure reason, offered in the early-closure modal only, and which mixed two questions (was it real? where did it come from?).

## Decision Drivers

- Tell a real incident from a non-incident, everywhere the status is read (API, reports, metrics, Jira).
- Record where a real incident comes from, whenever it is closed, without slowing the Commander down.
- Keep the partner list bounded (usable in statistics) while letting a Commander add a missing partner.
- Keep the Jira ticket consistent with the incident, in both directions, without new Jira configuration.

## Decision

### 1. A terminal `REJECTED` status

`IncidentStatus.REJECTED = 70`, after `CLOSED` so that `status < CLOSED` keeps meaning "still open" and `status >= CLOSED` (`IncidentStatus.is_terminal`) means "finished". An incident is rejected by closing it with a reason meaning it was not a real incident: `duplicate`, `false_positive`, `superseded`, `cancelled`. A closure with `resolved` stays `CLOSED`.

Closing early (before mitigation) is only for non-incidents: the early-closure modal offers the rejection reasons only, and every early closure rejects. A real incident is never closed early, even one caused by a partner while we wait for its fix: it follows the normal workflow, is mitigated once the fix is in, then closed. Accordingly, `Incident.can_be_closed` only lets a rejection reason skip the workflow (`resolved` and the deprecated `external` no longer do), and a modal submitted with another reason is refused. Rejected incidents are counted apart in the status chart and kept out of the time-to-X metrics.

### 2. An origin independent of the status

`Incident.origin` (`internal` by default, or `partner`) and `Incident.partner` (a `Partner`, possibly empty for historical data). The origin only describes a real incident: it is never asked when rejecting, and on a rejected incident it is ignored, whatever was recorded before.

It is recorded where the Commander describes what happened:

| Surface | Role |
|---|---|
| Key Events message, posted at mitigation | main capture (origin + partner list) |
| Edit modal | any time, e.g. a provider outage known from the start |
| Close modal | confirmation, pre-filled; may be corrected after the post-mortem |

Each change is recorded as an `IncidentUpdate` (`event_type="origin_updated"`, with its author) and posted in the incident channel. The `external` closure reason is deprecated: it is no longer offered, and historical incidents closed with it become `CLOSED` with origin `partner`.

### 3. A bounded but extensible partner list

`Partner` (name unique case-insensitively, slug, `is_active`, `is_reviewed`) is curated in the admin. A Commander can type a partner that is not in the list: a matching name is reused, otherwise the partner is created *not reviewed* and the support conversation (tag `dev_firefighter`) is asked to review it. The admin can deactivate a partner (it stays on past incidents) or merge duplicates. An initial list is loaded with `manage.py create_partners NAME...`.

### 4. Jira mapping

- **IMPACT → Jira, REJECTED**: the workflow's reject transition (`RAID_JIRA_REJECT_TRANSITION`, default `Reject`) is applied on purpose, with the select field it requires (`RAID_JIRA_REJECT_REASON_FIELD`) set from `RAID_JIRA_REJECT_REASON_VALUES`, and a comment carrying the exact reason, reference and message (the Jira field only has coarse options). The ticket is then closed. This transition is never taken by the automatic path-finder.
- **Jira → IMPACT**: a ticket whose resolution is `RAID_JIRA_REJECTED_RESOLUTION` (default `Rejected`) rejects its incident instead of mitigating or closing it, with `duplicate` when the reject reason maps to it and `false_positive` otherwise.
- **Origin**: mirrored as labels on the ticket, `partner-caused` and `partner:<slug>`, which need no Jira configuration and can be filtered in JQL.

## Considered Options

- **Keep `CLOSED` and derive "rejected" from `closure_reason`**: no migration of the status, but every consumer (API clients, BI, reports) would have to learn the rule; the status alone would keep lying.
- **Use the existing `ignore` flag**: it hides incidents but says nothing about why, and is also used for the downgrade workflow.
- **A dedicated Jira field for the origin**: cleaner in Jira, but depends on Jira administrators; labels work today and a field can replace them later.
- **Let the early-closure modal close a real incident ("Yes, already resolved") and ask its origin there**: tried during the review, dropped. A real incident is mitigated before being closed; asking an origin in a form that otherwise rejects confused Commanders, and the historical `external` early closures were real partner incidents that should have been mitigated.
- **Record the origin only at closure**: too late for P1/P2 (closure comes after the post-mortem), and closure is not always done by whoever knew the cause.

## Consequences

### Positive

- The status tells real incidents from non-incidents for every consumer, and the metrics stop counting duplicates and false alarms.
- Incidents and metrics can be broken down by partner.
- The Jira ticket of a rejected incident is rejected, not resolved, and a rejection in Jira no longer sends the incident back to Mitigated.

### Negative

- API consumers filtering on the `Closed` label no longer see rejected incidents: they show as `Rejected`.
- Historical figures change slightly once the backfill migration runs (incidents closed with a non-incident reason since closure reasons exist become `REJECTED`).
- With `internal` as the default, "really internal" and "not specified" cannot be told apart.

### Risks

- The Jira reject transition, its required field or its options may change: they are settings, and a refused transition is logged without closing the ticket.
- Slack static selects hold at most 100 options: enough for a curated list; an external select would be needed beyond.
