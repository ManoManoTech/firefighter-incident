# Incidents from Datadog alerts

!!! warning "Proposed, not available yet"
    This page describes the setup decided in [ADR-0002](../architecture/adr/0002-alert-webhooks-use-the-incidents-api.md), which is still a proposal. The route does not behave this way yet: see the [implementation notes](../architecture/alert-incidents-implementation.md).

A Datadog monitor can open a FireFighter incident when it alerts. Datadog calls FireFighter through one webhook; each monitor says, with its tags and its priority, whether it opens incidents and where they go.

## What an alert creates

| Created | When |
|---|---|
| An incident, with a service user as creator and Commander | Always |
| Impacts, all *N/A* | Always |
| A Jira ticket, linked to the incident | Always |
| A Slack channel, with the responders linked to the category invited | P1–P3 only |

While the incident of a monitor is open, further alerts of that monitor create nothing. Once it is closed, the next alert opens a new incident. FireFighter does not close the incident when the alert recovers: the responders do.

## Set up FireFighter, once

1. Create a user for the integration, with the `incidents.add_incident` permission and nothing else.
2. Create an API token for that user, and store it as a secret.
3. Make `POST /api/v2/firefighter/incidents` reachable by Datadog, which calls from the internet. Publish that exact path and method only, and keep the rest of the API private.

## Set up Datadog, once

### The webhook

In *Integrations > Webhooks*, create one webhook:

- **URL**: `https://<firefighter host>/api/v2/firefighter/incidents`
- **Custom headers**:

    ```json
    {"Authorization": "Bearer <token>", "Content-Type": "application/json"}
    ```

- **Payload**:

    ```json
    {
      "title": "$EVENT_TITLE",
      "description": "A Datadog monitor is alerting and opened this incident automatically. Nobody has looked at it yet: please take ownership and investigate.\n\nWhat fired: $ALERT_STATUS\nWhere: $ALERT_SCOPE\n\nAlert: $LINK\nMonitor: https://<datadog site>/monitors/$ALERT_ID",
      "priority": "$ALERT_PRIORITY",
      "incident_category_id": "$TAGS[incident_category]",
      "environment": "$TAGS[env]",
      "dedup_key": "datadog-monitor-$ALERT_ID"
    }
    ```

The description is a text of the webhook, not the message of the alert: an alert message is written for a notification, can be long, and carries mentions that mean nothing in an incident. It says that a monitor opened the incident, gives what fired and where, and links to the alert (with its full message) and to the monitor.

### The notification rule

In *Monitors > Settings > Notification rules*, create one rule:

- **Scope**: `impact:true`
- **Recipient**: the webhook, as a conditional recipient notified on *Alert* only.

With this rule no monitor message has to mention the webhook, and a warning, a recovery or a missing-data notification does not call it.

### A monitor on rejected calls

Datadog does not retry a call that FireFighter rejects. Create a monitor on the 4xx answers of the route, so that a rejected alert is seen instead of lost.

## Opt a monitor in

Set this on the monitor. Its message does not change.

| On the monitor | Role | If missing |
|---|---|---|
| Tag `impact:true` | Opt-in | The monitor creates no incident |
| Priority, P1 to P3 | Priority of the incident | P3 |
| Tag `incident_category:<category id>` | Category of the incident: who is invited, and the category of the Jira ticket | The default category |
| `env:<environment value>`, such as `env:prd`, on the monitored data or as a tag of the monitor | Environment of the incident | The default environment |

- **Only P1 to P3 monitors opt in**, for now. Nothing enforces it: a P4 or P5 monitor tagged `impact:true` creates an incident and a Jira ticket, without a Slack channel.
- **The category is an id**, to look up in FireFighter: a category name is not unique and does not survive as a Datadog tag. The tag key is `incident_category` and not `category`, a common key that monitors may already use for something else.- **The environment** is a FireFighter environment value. `prod` is read as `prd`. An alert must carry a single `env` value: when the monitor is tagged with one value and the data it watches carries another, Datadog sends the last of the two in alphabetical order, which may be neither the one you meant. Tag the monitor with the same value as its data, or only when the data has none.
- **Keep the name of the monitor short.** Datadog puts the priority, the transition and the group that fired in front of it in the title, as in `[P3] [Triggered on {env:prd}] name`, and FireFighter truncates a title at 128 characters.

The monitors that create incidents are found by filtering the monitor list on `impact:true`.

## When an incident opens

FireFighter posts a message in the incident channel, asking one of the responders to take the Commander role and to check the priority, the category, the title, the summary and the environment, which come from the monitor. When FireFighter had to replace a value, the summary says which one.

The impacts stay *N/A*: nothing changes them after the declaration.
