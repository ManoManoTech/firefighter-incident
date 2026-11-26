# ADR-0002: Alert webhooks create incidents through `POST incidents`

**Status**: Proposed
**Date**: 2026-11-25

## Context

Monitoring tools fire alerts when something breaks, and some alerts deserve an incident. Today a person reads the alert and declares the incident by hand, in Slack. We want a Datadog monitor to declare it directly, through a webhook.

A Datadog webhook is a static template: a URL, fixed headers and a JSON body in which Datadog replaces variables. It cannot sign a request, compute a value or map one value to another. It retries on a server error or a missed connection, not on a client error.

FireFighter already exposes a route that creates an incident for a machine, `POST /api/v2/firefighter/incidents`: a static bearer token, a flat JSON body, and a `dedup_key` that returns the open incident instead of creating a second one. The other routes do not fit: the Slack route only accepts requests signed by Slack, the web form needs a login session, and `POST raid/jira_bot` creates a Jira ticket, not an incident.

But an incident created through this route is poorer than one declared in Slack: it has no impacts and no Jira ticket, and it opens a Slack channel whatever its priority, where a Slack declaration opens one for P1–P3 only.

## Decision Drivers

- Deliver the feature: a Datadog alert creates an incident, with no manual step.
- An incident raised by an alert is handled like any other incident.
- Work with what a webhook can send: a static header and a templated JSON body.
- Never lose an alert, and never create two incidents for one.
- Add no new component and no new way to create an incident.

## Decision

### 1. Alerts use the existing route

A Datadog webhook creates incidents by calling `POST /api/v2/firefighter/incidents`. No route is added, and no service sits between Datadog and FireFighter.

### 2. The route creates a complete incident

One call creates what a Slack declaration creates: the incident, its impacts, a Jira ticket linked to it for every priority and, for P1–P3 only, a Slack channel. The route reuses the steps of the Slack declaration instead of copying them. This changes the route for every caller, not only for alerts; it has no callers today, which has been checked.

Nobody assesses the impacts of an alert, so they are recorded as *N/A*.

### 3. The route replaces bad data instead of rejecting it

Datadog does not retry a client error: an alert rejected for its data would open no incident, and nobody would know. So when a value sent by a caller is missing or cannot be used, the route replaces it with a default, says so in the incident, and creates the incident. It only rejects what it cannot repair, such as a bad token or an unreadable body, and those rejections are monitored.

### 4. One open incident per monitor

The `dedup_key` identifies the monitor. Retries, re-notifications and a flapping monitor return the open incident; once it is closed, the next alert opens a new one. A multi-alert monitor firing for a second group while its incident is open creates nothing.

### 5. Monitors opt in, and carry their own routing

Not every monitor creates incidents: a monitor opts in explicitly, and only its trigger calls the webhook, not its recovery. For now only P1 to P3 monitors opt in.

There is a single webhook. The priority, the category and the environment of the incident are not written in it: each monitor carries them, and the webhook reads them from the alert.

### 6. Responders take ownership

The creator of the incident is the user of the token, a service user, and not a person. FireFighter asks the responders invited to the incident channel to take the Commander role and to complete what the alert could not provide.

### Not decided here

- **One declaration service** shared by the Slack modal, the API and the web form. It would remove the remaining duplication, but the feature does not need it.
- **The web form**, which keeps its current result.
- **Closing the incident when the alert recovers.**
- **Changing the impacts after the declaration**, which no modal allows today.
- **Adding later groups of a multi-alert monitor to its open incident.**
- **Reporting the incident back to Datadog.**

## Considered Options

- **Use `POST incidents` as it is**: configuration only, but alert incidents would have no impacts and no Jira ticket, and a P4 or P5 would open a Slack channel.
- **Extract one declaration service first**, then align the route: the cleanest code, but a refactor of every entry point before the feature can ship.
- **A dedicated route for alerts**: would protect existing callers of `POST incidents`, but the route has none, and it adds another way to create an incident.
- **A receiver service** between Datadog and FireFighter: allows any mapping, but it is a component to build, deploy and operate.
- **Reject what breaks the rules of the declaration form**: consistent with a declaration by a person, but a person sees the error and corrects it, while a rejected alert is lost.
- **One open incident per monitor and group**: unrelated causes get their own incident, but a monitor grouped by host whose forty hosts fail from one cause opens forty incidents.
- **One webhook per combination of priority, category and environment**: no change to the route, but the webhooks multiply and each holds ids to keep in line with FireFighter.
- **Mention the webhook in the message of each monitor**: the opt-in is visible in the monitor, but every message has to be edited, and a forgotten condition calls the webhook on recoveries too.

## Consequences

### Positive

- An incident raised by an alert is complete: impacts, a Jira ticket, and a Slack channel when its priority calls for one.
- One route creates incidents for every machine, and what it creates does not depend on whether a person or a machine declared the incident.
- An alert with imperfect data still opens an incident, flagged as such, instead of being dropped.
- Duplicate protection already exists and is enforced by the database.
- The webhook is answered before Slack and Jira are called, so a slow Slack or Jira does not cause a retry.

### Negative

- The route changes behaviour: a Jira ticket for every incident, no channel for P4–P5, and replaced values where it used to reject.
- A replaced value can put an incident in the wrong category, environment or priority: the wrong team is invited, or a P1 is opened as a P3.
- The impacts of an incident raised by an alert are never assessed: reports on impacts count these incidents as having none.
- No person commands the incident until a responder takes the role, and the request to do so can be ignored.
- A multi-alert monitor firing for a second group leaves no trace in its open incident.
- Datadog does not know that an incident was created: a webhook is one-way.
- The Slack modal and the API share steps but not yet one code path, and the web form still differs.

### Risks

- A noisy monitor that opts in opens real incidents and invites people. The opt-in and the limit to P1–P3 are the only guards, and the limit is a convention that nothing enforces.
- The Slack channel and the Jira ticket are created after the answer: if one fails, the incident exists and the webhook already got its answer. Failures need monitoring.
- The token is the only credential, and the route has to be reachable from the internet. A leaked token allows creating incidents until it is revoked.
- The design relies on Datadog behaviour that is documented but not yet observed end to end. It is listed, with the other points to settle before this decision is accepted, in the implementation notes.

## Related documents

- [Incidents from Datadog alerts](../../usage/datadog-alerts.md): how to set up Datadog and a monitor.
- [Implementation notes](../alert-incidents-implementation.md): what to build, and what to confirm before accepting this decision.
