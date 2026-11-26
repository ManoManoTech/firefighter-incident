# Incidents from alerts: implementation notes

Working notes for [ADR-0002](adr/0002-alert-webhooks-use-the-incidents-api.md): what to build, and what to settle before the decision is accepted. They are meant to become tickets, and to be removed once the work is done. The setup seen from Datadog is in [Incidents from Datadog alerts](../usage/datadog-alerts.md).

## To settle before accepting the ADR

- [ ] **Monitor tags in the webhook.** Existing alert events carry the tags of their monitor, of the group that fired and of the query scope, and Datadog documents `$TAGS` as the tags of the event. One real call has to confirm that `$TAGS[category]` and `$TAGS[env]` are filled.
- [ ] **Two `env` values.** `env` is a tag key reserved by Datadog. What `$TAGS[env]` gives when the monitor and the monitored service carry different values was not observed.
- [ ] **A webhook as the recipient of a notification rule.** The API takes recipients in the format of a monitor mention, with a condition on the transition (`transition_type:is_alert`); a webhook handle fits, but no existing rule uses one. Fallback: mention the webhook in the message of each opted-in monitor, inside its alert condition.
- [ ] **`$ALERT_STATUS` and `$ALERT_SCOPE`.** They are not filled the same way by every type of monitor (a logs monitor needs the status added by hand), and one may come out empty.
- [ ] **The default category.** FireFighter has a default environment and a default priority (a `default` flag on each), but no default category. An existing category has to be designated, not a new one created: which one, and how (a `default` flag, or a setting). Until then a missing or unusable category is rejected.
- [ ] **The title prefix.** `$EVENT_TITLE` is `[Triggered on {group}] name of the monitor`. With a long group it passes 128 characters and the truncation cuts the name. Either monitors keep short names and groups, or the route drops the prefix.

## What to build

### 1. The route creates a complete incident

| Rule | Today | Target |
|---|---|---|
| Impacts | None | Every impact *N/A*; the business impact of the Jira ticket is then left empty |
| Platform | Not set | All |
| Slack channel | Every priority | P1–P3 only |
| Jira ticket | No | Yes, for every priority, linked to the incident |
| `dedup_key` | An open match returns 200 | Unchanged, and checked before anything else: a match creates no impacts, channel or ticket |

The route still answers 201 as soon as the incident and its impacts are saved. The Slack channel and the Jira ticket are created after the answer, as the channel is today. If one fails, it is logged at error level.

The steps of the Slack declaration are reused:

| Step | Today | For the route |
|---|---|---|
| Impacts | `SelectImpactForm(impacts).save(incident=...)`, callable from anywhere | Called as it is |
| Slack channel | The `create_incident_conversation` signal, which the route already sends | Sent for P1–P3 only (`priority.value <= 3`, the test the Jira step already uses) |
| Jira ticket | `UnifiedIncidentForm._create_jira_ticket`, a private method of the Slack declaration form | Extracted |

`_create_jira_ticket` takes the incident, the creator and the impacts as arguments; the only thing it reads from the form is `self._jira_extra_fields`. So:

1. Move its body, unchanged, to a function in the `raid` app: `create_jira_ticket_for_incident(incident, creator, impacts_data, jira_extra_fields)`.
2. `UnifiedIncidentForm` calls that function with its `_jira_extra_fields`. A Slack declaration behaves as before, and the existing tests of the form cover the move.
3. The route calls the same function after its answer, once the channel step is done, with the default platform and the incident's environment as extra fields. Only when `ENABLE_RAID` is set.

### 2. What the route accepts

- `created_by_email` becomes optional. When absent, the creator is the user of the bearer token.
- `priority`: the priority value, as `P2` or `2`. An alternative to `priority_id`.
- `environment`: the environment value, matched without regard to case. An alternative to `environment_id`.
- `incident_category_id`: unchanged.

### 3. Replace instead of reject

| Value | Problem | The route |
|---|---|---|
| Title | Longer than 128 characters | Truncates it |
| Title | Shorter than the 10 characters the declaration form asks for | Accepts it |
| Description | Longer than 1200 characters | Truncates it |
| Priority | Missing | Uses P3 |
| Environment | Missing | Uses the default environment |
| Environment | `prod` | Reads it as `prd` |
| Category | Missing, unknown or disabled for creation | Uses the default category, once one is designated |

When a value was replaced, a line added at the end of the description says which one.

Still rejected: a missing or invalid token, a body that is not valid JSON, an empty title, and a priority or an environment that is given but unknown. Rejected calls are logged with their `dedup_key`.

### 4. Jira reporter for a user without a Jira account

The reporter of the Jira ticket is the creator's Jira account. A service user has none: the lookup raises `JiraUserNotFoundError`, which `raid.service.get_jira_user_from_user` does not catch (it falls back to the default reporter only on `JiraAPIError`), so the ticket would never be created. Fall back to the default reporter, `RAID_DEFAULT_JIRA_QRAFT_USER_ID`, in that case too.

### 5. The ownership message

When the creator of an incident has no Slack account, post a message in the incident channel, addressed to the responders invited through the category. It asks one of them to take the Commander role, with a button that assigns the role to whoever clicks it, and lists what to check:

| Data | Value on an alert incident | Completed with |
|---|---|---|
| Commander, and any other required role | The service user | The button, or the *Update roles* modal |
| Priority and category | From the monitor, or replaced | The *Update status* modal |
| Title and summary | The alert title and the text of the webhook | The *Edit* modal |
| Environment | From the monitor, or the default | The *Edit* modal |

The condition is the missing Slack account, not Datadog: the message serves any machine that creates incidents through the route. It does not ask for the impacts or for the customer and seller references, which no modal changes after the declaration.

## Order

1. Settle the points above with one test monitor.
2. Extract the Jira step (no behaviour change), then the Jira reporter fallback.
3. Change the route: complete incident, accepted fields, replacement rules.
4. The ownership message.
5. Set up Datadog, and opt in one or two P3 monitors before any P1.
