# Incidents from alerts: implementation notes

Working notes for [ADR-0002](adr/0002-alert-webhooks-use-the-incidents-api.md): what to build, and what to settle before the decision is accepted. They are meant to become tickets, and to be removed once the work is done. The setup seen from Datadog is in [Incidents from Datadog alerts](../usage/datadog-alerts.md).

## To settle before accepting the ADR

- [x] **Monitor tags in the webhook.** Confirmed with a test monitor: `$TAGS[incident_category]` gives the value of the monitor's tag, and `$ALERT_PRIORITY` gives the priority as `P3`.
- [x] **Two values for one tag key.** Observed: the webhook sends one value, the last in alphabetical order. A monitor tagged `env:prd` on data in `env:stg` sends `stg` in `$TAGS[env]`; tagged `env:zzz` on the same data, it sends `zzz`. Neither the monitor nor the data wins as such. Consequence: an alert must carry a single `env` value, so the setup guide asks for no `env` tag on a monitor whose data already carries one. In every test call the monitor was tagged too: a call where the `env` of the data is the only value was not observed, though the data's value was in `$TAGS` each time.
- [ ] **A webhook as the recipient of a notification rule.** The API takes recipients in the format of a monitor mention, with a condition on the transition (`transition_type:is_alert`); a webhook handle fits, but no existing rule uses one. Creating a rule needs a Datadog permission that monitor owners may not have, so it could not be tested: to confirm with a Datadog administrator. The fallback is confirmed: a mention of the webhook inside the alert condition of the monitor message calls it on the trigger and not on the recovery.
- [ ] **`$ALERT_STATUS` and `$ALERT_SCOPE`.** Observed on a metric monitor and a logs monitor. `$ALERT_STATUS` is a full sentence with the metric, its scope and the threshold for a metric monitor, and is empty for a logs monitor. `$ALERT_SCOPE` is empty for a simple alert and gives the group (`env:stg`) for a multi alert. So either line of the description can be blank, and both are for a logs monitor that is a simple alert. To decide: accept blank lines, since the links are always there, or have the route drop a line whose value is empty. Other types of monitor were not observed.
- [x] **One call per group.** Observed: a multi-alert monitor whose two groups trigger together calls the webhook twice, a fraction of a second apart. The `dedup_key` makes the second call return the incident of the first, and which group gives the incident its title is a matter of arrival order. A group can also have an empty value, which gives a title such as `[Triggered on {env:}] name`.
- [ ] **The default category.** FireFighter has a default environment and a default priority (a `default` flag on each), but no default category. An existing category has to be designated, not a new one created: which one, and how (a `default` flag, or a setting). Until then a missing or unusable category is rejected.
- [ ] **The title prefix.** Observed: `$EVENT_TITLE` is `[P3] [Triggered on {group}] name of the monitor`, the priority coming first when the monitor has one, and `[P3] [Triggered] name` for a simple alert. With a long group it passes 128 characters and the truncation cuts the name. Either monitors keep short names and groups, or the route drops the prefix.

### Observed on existing monitors

Read from existing monitors and the alert events they produced, before the test with a webhook. An event shows what Datadog holds, not what a webhook sends: the test above gave the rest.

- **Monitor tags reach the alert event**, on triggers and on recoveries, for the log monitors observed.
- **A key carried by both the monitor and the group gives two values.** A monitor tagged `service:a` and grouped by service produces events with `service:a` and `service:b`. The test confirmed the same for `env`.
- **`category` is already used as a tag key** by monitors, for another purpose. The category tag is therefore `incident_category`. No alert event carries an `impact` tag.
- **Tag values are rewritten on the event**: a value starting with `@` arrives with `_` instead. A category id, a UUID, is not affected.
- **Titles pass 128 characters in practice**: a monitor grouped by service, with the service repeated in its name, gives a title of about 140 characters.

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
| Environment | Unknown, such as a mistyped tag or the empty value of a group | Uses the default environment |
| Category | Missing, unknown or disabled for creation | Uses the default category, once one is designated |

When a value was replaced, a line added at the end of the description says which one.

Still rejected: a missing or invalid token, a body that is not valid JSON, an empty title, and a priority that is given but unknown. Rejected calls are logged with their `dedup_key`.

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

1. Settle the points still open above. The test with real monitors is done: what remains is one question for a Datadog administrator and three choices.
2. Extract the Jira step (no behaviour change), then the Jira reporter fallback.
3. Change the route: complete incident, accepted fields, replacement rules.
4. The ownership message.
5. Set up Datadog, and opt in one or two P3 monitors before any P1.
