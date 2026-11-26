# ADR-0002: Alert webhooks create incidents through `POST incidents`

**Status**: Proposed
**Date**: 2026-11-25

## Context

Monitoring tools fire alerts when something breaks, and some alerts deserve an incident. Today a person reads the alert and declares the incident by hand, in Slack. We want a Datadog monitor to declare it directly, through a webhook.

A Datadog webhook is a static template: a URL, fixed headers and a JSON body in which Datadog replaces variables. Some describe the alert (`$EVENT_TITLE`, `$ALERT_ID`, `$ALERT_PRIORITY`), and `$TAGS[key]` gives the value of one tag of the event, or an empty string when the tag is absent. A webhook cannot sign a request, compute a value or map one value to another. A request times out after 15 seconds and is retried on a 5xx answer or a missed connection, not on a client error.

FireFighter already exposes a route that creates an incident for a machine, `POST /api/v2/firefighter/incidents`: a static `Authorization: Bearer <token>` header, a flat JSON body, and an optional `dedup_key` (while an incident with this key is open, posting it again returns that incident with 200 and creates nothing). The other routes do not fit: the Slack route only accepts requests signed by Slack, in Slack's format; the web form needs a login session; `POST raid/jira_bot` creates a Jira ticket, not an incident.

But an incident created through this route is poorer than one declared in Slack:

| | Declared in Slack | `POST incidents` today |
|---|---|---|
| Impacts | Yes | No |
| Slack channel | P1–P3 only | Every priority |
| Jira ticket | Yes, linked to the incident | No |
| Creator | The person who declares | `created_by_email`, required; an unknown address creates a user |

The Slack declaration is the intended rule: every incident gets impacts and a Jira ticket, and only P1–P3 get a Slack channel. An incident raised by an alert must be handled like any other, so the route has to follow that rule too.

## Decision Drivers

- Deliver the feature: a Datadog alert creates an incident, with no manual step.
- An incident raised by an alert is a complete incident: impacts, a Jira ticket, and a Slack channel for P1–P3 only.
- Work with what a webhook can send: a static header and a templated JSON body.
- Never create two incidents for one alert, whatever the retries and re-notifications.
- Add no new component and no new way to create an incident.

## Decision

A Datadog webhook creates incidents by calling `POST /api/v2/firefighter/incidents`. One call creates an incident, its impacts, a Jira ticket linked to it and, for P1–P3 only, a Slack channel. No other route is added.

### 1. What one call to `POST incidents` creates

| Created | When |
|---|---|
| Incident, with the token's user as creator and Commander | Always |
| Impacts, all *N/A* | Always |
| Jira ticket, linked to the incident | Always, for every priority |
| Slack channel, with the responders linked to the category invited | P1–P3 only |

A call whose `dedup_key` matches an open incident creates nothing and returns that incident.

This changes the route as follows:

| Rule | Before | After |
|---|---|---|
| Impacts | None | Every impact (business, customers, sellers, employees) is *N/A*: nobody assessed them. The business impact field of the Jira ticket is therefore left empty. They stay as they are (see 10). |
| Platform | Not set | All |
| Slack channel | Every priority | P1–P3 only |
| Jira ticket | No | Yes, for every priority, linked to the incident |
| Validation | Title up to 128 characters, no other check; anything invalid is rejected | Tolerant: a value that is missing or cannot be used is replaced instead of rejected (see 9) |
| Priority and environment | By id only | By id or by value (see 5) |
| Description | No limit | Truncated to 1200 characters instead of rejected, since a rejected call is not retried. The description sent by the alert webhook is short (see 5) and is not expected to be truncated. |
| `dedup_key` | An open match returns 200 | Unchanged, and checked before anything else: a match creates no impacts, channel or ticket |

The route still answers 201 as soon as the incident and its impacts are saved. The Slack channel and the Jira ticket are created after the answer, as the channel is today.

The route reuses the steps of the Slack declaration instead of copying them. Two of the three can be called as they are; the Jira step cannot, and is extracted:

| Step | Today | For the route |
|---|---|---|
| Impacts | `SelectImpactForm(impacts).save(incident=...)`, callable from anywhere | Called as it is, with every impact *N/A* |
| Slack channel | The `create_incident_conversation` signal, which the route already sends | Sent for P1–P3 only (`priority.value <= 3`, the test the Jira step already uses) |
| Jira ticket | `UnifiedIncidentForm._create_jira_ticket`, a private method of the Slack declaration form | Extracted, see below |

`_create_jira_ticket` creates the Jira issue and the linked `JiraTicket`, copies the impacts to it, sets the watchers, links the ticket to the incident and to its channel, and sends the announcements. It takes the incident, the creator and the impacts as arguments; the only thing it reads from the form is `self._jira_extra_fields`. The extraction is therefore small:

1. Move its body, unchanged, to a function in the `raid` app, where everything it calls already lives: `create_jira_ticket_for_incident(incident, creator, impacts_data, jira_extra_fields)`.
2. `UnifiedIncidentForm` calls that function with its `_jira_extra_fields`. A Slack declaration behaves exactly as before, and the existing tests of the form cover the move.
3. The route calls the same function after its answer, once the channel step is done (the ticket is linked to the channel when there is one), with the default platform and the incident's environment as extra fields. It does so only when `ENABLE_RAID` is set: without the `raid` app, the route creates no Jira ticket.

Nothing else moves. Extracting one declaration service shared by every entry point is not required for this and is not part of this decision.

### 2. The creator is the user of the token

`created_by_email` becomes optional. When it is absent, the creator is the user the Bearer token belongs to.

### 3. Jira reporter for users without a Jira account

The reporter of the Jira ticket is the creator's Jira account. A service user has none: the lookup raises `JiraUserNotFoundError`, which `raid.service.get_jira_user_from_user` does not catch (it falls back to the default reporter only on `JiraAPIError`), so the ticket would never be created. The lookup falls back to the default reporter, `RAID_DEFAULT_JIRA_QRAFT_USER_ID`, for a user without a Jira account too.

### 4. One service user and one token

The integration gets a dedicated user with the `incidents.add_incident` permission and nothing else, and an API token for it. The webhook sends the token in a custom header, `Authorization: Bearer <token>`, and sends no creator.

### 5. One webhook; the monitor carries the routing

There is a single webhook. The priority, the category and the environment are not written in its template: each monitor carries them, and the template reads them from the alert.

| Incident field | Set on the monitor as | Read by the webhook as |
|---|---|---|
| Priority | The monitor's own priority (P1 to P3, see 7) | `$ALERT_PRIORITY` |
| Category | Tag `category:<category id>` | `$TAGS[category]` |
| Environment | Tag `env:<environment value>` | `$TAGS[env]` |

```json
{
  "title": "$EVENT_TITLE",
  "description": "A Datadog monitor is alerting and opened this incident automatically. Nobody has looked at it yet: please take ownership and investigate.\n\nWhat fired: $ALERT_STATUS\nWhere: $ALERT_SCOPE\n\nAlert: $LINK\nMonitor: https://<datadog site>/monitors/$ALERT_ID",
  "priority": "$ALERT_PRIORITY",
  "incident_category_id": "$TAGS[category]",
  "environment": "$TAGS[env]",
  "dedup_key": "datadog-monitor-$ALERT_ID"
}
```

The description is a text written in the webhook template, not the message of the alert. It has three parts:

- a fixed sentence: a monitor opened the incident and someone has to take care of it;
- two facts that Datadog fills in and that point at the problem: `$ALERT_STATUS`, its one-line summary of what crossed which threshold, and `$ALERT_SCOPE`, the tags the alert fired for (a service, a host, a region);
- two links: the alert itself (`$LINK`, with its full message), then its monitor (current state, query and history).

The message of the alert, `$EVENT_MSG`, is left out: it is written for a notification, can be long, and carries mentions and formatting that mean nothing in an incident. What is kept is short, so the description is not truncated.

A webhook cannot map values, so the route accepts what a monitor can carry, next to the ids it takes today:

- `priority`: the priority value, as `P2` or `2`. An alternative to `priority_id`.
- `environment`: the environment value (its short unique code), matched without regard to case: Datadog normalizes some tags to lowercase, and FireFighter's values are uppercase. An alternative to `environment_id`. Datadog uses the same `env` tag for the environment of the monitored services, where the spelling `prod` is common: `prod` is accepted as an alias of `prd`.
- `incident_category_id`: unchanged. The category is given by its id: a category name is not unique and does not survive as a tag (Datadog converts spaces and most punctuation to underscores, and may lowercase the value), while an id is a valid tag value (letters, digits and hyphens) and survives a rename.

What happens when one of these values is missing or cannot be used is described in 9.

The category is the only routing input, as for a manual declaration: it decides who is invited to the channel (the Slack user groups and channels linked to the category) and the category of the Jira ticket.

### 6. One open incident per monitor

`dedup_key` is built from the monitor id. Retries, re-notifications and a monitor that flaps all return the open incident instead of creating another one. Once that incident is closed, the next alert of the same monitor creates a new one.

This holds for a multi-alert monitor too: while its incident is open, an alert for another group creates nothing and adds nothing to the incident.

### 7. A monitor opts in with a tag, and only its trigger calls the webhook

Not every monitor creates incidents. A monitor opts in by carrying the tag `impact:true`; the others never call the webhook.

For now only monitors of priority P1 to P3 opt in: a P4 or P5 alert is too low a priority to open an incident by itself, and stays a notification. Every incident raised by an alert therefore gets a Slack channel. The route itself keeps the general rule for every priority (see 1), for its other callers.

The webhook is not mentioned in any monitor message. One Datadog monitor notification rule does the routing:

- its scope is `impact:true`, matched against the tags of the monitor;
- its recipient is the webhook, as a conditional recipient notified on the *Alert* status only.

A monitor notifies on every transition, including the recovery; with this condition a warning, a recovery or a missing-data notification does not call the webhook. FireFighter does not close an incident when the alert recovers: the responders do.

Opting a monitor in is therefore a matter of tags and of its priority, with no change to its message:

| On the monitor | Role |
|---|---|
| Tag `impact:true` | Opt-in |
| Priority, P1 to P3 only | Priority of the incident |
| Tag `category:<category id>` | Category of the incident |
| Tag `env:<environment value>` | Environment of the incident, optional |

### 8. Exposure

Datadog calls from the internet. A deployment publishes `POST` on the exact path `/api/v2/firefighter/incidents` alone, and keeps the read endpoints and the rest of the API private.

### 9. An alert with bad data still creates an incident

Datadog does not retry a client error. If the route rejected an alert because of its data, a real P1 would open no incident and nobody would know. So the route replaces what it can instead of rejecting:

| Value | Problem | The route |
|---|---|---|
| Title | Longer than 128 characters | Truncates it |
| Title | Shorter than the 10 characters the declaration form asks for | Accepts it: the minimum does not apply to the route |
| Priority | Missing (the monitor has no priority) | Uses P3 |
| Environment | Missing | Uses the default environment |
| Environment | `prod` | Reads it as `prd` |
| Category | Missing, unknown or disabled for creation | Uses the default category (see below) |

When a value was replaced, a line added at the end of the description says which one, so the responders know the routing may be wrong.

What is still rejected: a missing or invalid token, a body that is not valid JSON, an empty title, and a priority or an environment that is given but unknown. A Datadog monitor watches the 4xx answers of the route and notifies as soon as there is one, so a rejected alert is seen instead of lost.

**Open point: the default category.** FireFighter has a default environment and a default priority (a `default` flag on each), but no default category: nothing in the code designates one. An existing category has to be designated, not a new "triage" category created for this. Which category, and how it is designated (a `default` flag like the other two, or a setting), is to be settled before the implementation. Until then a missing or unusable category is rejected, and caught by the monitor on 4xx answers.

### 10. The responders are asked to take ownership

A person who declares an incident becomes its Commander and has answered the declaration questions. An alert does neither: the service user holds every required role, and the questions are answered with defaults. So when the creator of an incident has no Slack account, FireFighter posts a message in the incident channel, addressed to the responders invited through the category. It asks one of them to take the Commander role, with a button that assigns the role to whoever clicks it, and lists what the Commander has to complete:

| Data | Value on an alert incident | Completed with |
|---|---|---|
| Commander, and any other required role | The service user | The button of the message, or the *Update roles* modal |
| Priority and category | From the monitor, or replaced (see 9) | The *Update status* modal |
| Title and summary | The alert title, and the text of the webhook: what fired, where, and the two links | The *Edit* modal |
| Environment | One, from the monitor or the default | The *Edit* modal |

The condition is the missing Slack account of the creator, not Datadog: the message serves any machine that creates incidents through the route.

The message does not ask for the impacts, nor for the customer and seller references (Zendesk ticket, seller contract, key account, golden list, Zoho Desk ticket): they are asked once, in the declaration modal, and no modal changes them afterwards. An alert incident keeps its *N/A* impacts and has no such reference.

### Not decided here

- **One declaration service** shared by the Slack modal, the API and the web form. It would remove the remaining duplication, but the feature does not need it.
- **The web form**, which keeps its current result (no impacts, no Jira ticket, a channel for every priority).
- **Closing the incident when the alert recovers.**
- **Changing the impacts after the declaration**: a modal for the impacts and the customer and seller references, whose changes reach the Jira ticket. It would let the Commander of an alert incident assess them.
- **Adding later groups to the open incident**: when a multi-alert monitor fires for a group its open incident has not seen, a note in the incident. It would remove the silent second group, but FireFighter would have to receive the group and remember the ones already noted.
- **Reporting the incident back to Datadog** (an event carrying the incident link, posted by FireFighter through Datadog's API). It would make the incident visible from the monitor, but it makes FireFighter depend on Datadog, and the feature works without it.

## Considered Options

- **Use `POST incidents` as it is**: configuration only, no code change, but alert incidents would have no impacts and no Jira ticket, and a P4 or P5 would open a Slack channel.
- **Extract one declaration service first**, then align the route: the cleanest code, but a refactor of every entry point before the feature can ship.
- **A dedicated route for alerts** (`POST alerts/incidents`) creating the incident, impacts, Jira ticket and channel: would protect existing callers of `POST incidents`, but the route has none, and it adds another way to create an incident while the general route keeps a poorer result.
- **One webhook per combination of priority, category and environment**, with the ids written in each template: no change to the fields the route accepts, but the number of webhooks grows with every combination, and each holds ids to keep in line with FireFighter's reference data.
- **One open incident per monitor and group**, with the group in the `dedup_key`: unrelated causes get their own incident, but a monitor grouped by host whose forty hosts fail from one cause opens forty incidents and forty Slack channels.
- **Apply the rules of the declaration form to the route and reject what breaks them** (title of 10 to 128 characters, every value present and valid): consistent with a declaration by a person, but a person sees the error and corrects it, while a rejected alert is not retried and is lost.
- **Send the alert message as the description** (`$EVENT_MSG`, after the two links): the incident describes the problem without a click, but alert messages are long, get truncated, and carry notification mentions and formatting.
- **Mention the webhook in the message of each monitor** that should create incidents: the opt-in is visible in the monitor, but every message has to be edited and has to restrict the mention to the alert condition itself; a forgotten condition calls the webhook on recoveries too.
- **A receiver service** between Datadog and FireFighter, translating alerts and calling the API: allows any mapping (a category by name, for instance), but it is a component to build, deploy and operate, and it would not add impacts or a Jira ticket.

## Consequences

### Positive

- An incident raised by an alert is complete: impacts, a Jira ticket, and a Slack channel when its priority calls for one.
- One route creates incidents for every machine, alerting tools included, and what it creates does not depend on whether a person or a machine declared the incident.
- Duplicate protection already exists and is enforced by the database.
- The webhook is answered before Slack and Jira are called, so a slow Slack or Jira does not cause a timeout and a retry.
- A caller no longer has to name a creator: the token identifies it.
- An alert with incomplete or imperfect data still opens an incident, flagged as such, instead of being dropped.

### Negative

- The route changes behaviour: a Jira ticket for every incident, no channel for P4–P5, and replaced values where it used to reject. It has no callers today, which has been checked, so nobody is affected.
- The category tag holds an id, which has to be looked up in FireFighter and is not readable in Datadog. A wrong id sends the incident to the default category or, until one is designated, creates no incident.
- Whether a monitor creates incidents is not visible in its message: it is decided by a tag and by a notification rule defined elsewhere in Datadog. The monitors that do are found by filtering the monitor list on `impact:true`.
- Datadog does not know that an incident was created: a webhook is one-way and its answer is ignored. The link exists in the other direction only: the incident's description gives the links to the alert and to its monitor, and FireFighter announces the incident in Slack as it does for any other.
- The impacts of an incident raised by an alert are never assessed: they are *N/A* and no modal changes impacts after the declaration. Reports on impacts count these incidents as having none, and their Jira ticket, like the post-mortem ticket that copies it, has no business impact.
- The description of an incident raised by an alert says what fired and where, in Datadog's terms (a metric, a threshold, tags), not what it means for users: nobody has assessed the problem when the incident opens. The explanation written by the owners of the monitor, in its message, is one click away, behind the link to the alert.
- The creator, a service user with no Slack account, becomes the Commander: no person holds the role until a responder takes it. The message asking for it (see 10) can be ignored: an incident may stay without a person in command.
- One open incident per monitor: a multi-alert monitor firing for a second group while the first incident is open does not create a second incident, and leaves no trace in the first. The incident describes the first group only; the others are seen on the monitor page, linked in the description.
- The Slack modal and the API share steps but not yet one code path, and the web form still differs.

### Risks

- A call that is still rejected (see 9) creates no incident, and Datadog does not retry it. The monitor on the 4xx answers of the route is what makes it visible: without that monitor the loss is silent.
- A replaced value creates an incident that may be in the wrong category, environment or priority: the wrong team is invited, or a P1 is opened as a P3. The line added to the description is the only signal.
- Until a default category is designated, an opted-in monitor without a valid `category` tag creates no incident.
- Limiting the opt-in to P1–P3 is a convention: the notification rule filters on tags, not on the monitor's priority, and the route accepts every priority. A P4 or P5 monitor tagged `impact:true` by mistake creates an incident and a Jira ticket, without a Slack channel.
- Datadog's documentation says a notification rule can notify "any integration channel", and its API takes the recipients of a rule in the same format as the mentions of a monitor message, with a condition on the transition (`transition_type:is_alert`). A webhook handle fits that format, but no existing rule uses one: that a webhook can be the conditional recipient of a rule is to be confirmed with a real monitor before this decision is accepted. If it cannot, the fallback is to mention the webhook in the message of each opted-in monitor, inside its alert condition.
- The routing relies on the monitor's tags being part of the tags of the event the webhook receives. Existing alert events were checked: an alert event carries the tags of its monitor, the tags of the group that fired and the tags of the query scope. Datadog documents `$TAGS` as the tags of the event, so the monitor's `category` and `env` tags are expected to reach the webhook; one real call remains to confirm it. What `$TAGS[env]` gives when the monitor and the monitored service carry two different `env` values was not observed: `env` is a tag key reserved by Datadog, and in the alerts checked both carried the same value.
- `$EVENT_TITLE` is not the name of the monitor alone: Datadog puts the transition and the group that fired in front of it (`[Triggered on {group}] name`). With a long group the title passes 128 characters, and the truncation cuts the end, which is the name of the monitor. This was observed on an existing alert. Monitors that opt in need short names and short groups, or the route has to drop that prefix: to be decided before the implementation.
- `$ALERT_STATUS` and `$ALERT_SCOPE` are not filled in the same way by every type of monitor (Datadog documents that a logs monitor needs the status added by hand), and one of them may come out empty. What they give for the types of monitor that will opt in is part of the test with a real monitor.
- The Slack channel and the Jira ticket are created after the answer: if one fails, the incident exists, the webhook already got 201 and nobody is told. Failures are logged at error level and need monitoring.
- The token is the only credential. A leaked token allows creating incidents until it is revoked and, while `created_by_email` exists, naming any creator or creating users. It is stored as a secret and rotated.
- A category without linked Slack user groups or channels produces an incident nobody from the owning team is invited to.
