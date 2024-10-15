
# Integrations

## :simple-pagerduty: PagerDuty

### Features

Expose the current on-call schedule, and allow anyone to escalate to PagerDuty.

![PagerDuty integration](../assets/screenshots/pagerduty_web_oncall_overview.png)
_Exposing the on-call schedule, even for users with no PagerDuty access._

![PagerDuty integration](../assets/screenshots/pagerduty_web_oncall_overview.png)
_Trigger a PagerDuty incident from the Web UI, even with no PagerDuty access._

![PagerDuty integration](../assets/screenshots/pagerduty_slack_trigger.png)
_In a Slack conversation about an incident, anyone can escalate to PagerDuty, with `/incident oncall`._

### Tasks

Tasks are provided to regularly sync the on-call schedules, services and users from PagerDuty, as well as a task to trigger PagerDuty incidents.

If Confluence is enabled, there is a task to export the on-call schedule to a Confluence page set with environment variable `CONFLUENCE_ON_CALL_PAGE_ID`.

See the [available PagerDuty tasks][firefighter.pagerduty.tasks] that can be [scheduled from the Back-Office](../deploy/XX-tasks.md).

### Settings and configuration

[Basic configuration with environment variables](../deploy/XX-settings.md#pagerduty-integration).

No Back-Office configuration.

## :fontawesome-brands-confluence: Confluence

!!! warning
    This integration is disabled by default, and is not yet documented.
    It is specific to our internal use case.

## :fontawesome-brands-slack: Slack

### Features

Open, manage and close incidents from Slack. The whole lifecycle.

![See current incidents from Slack](../assets/screenshots/slack_bot_home.jpeg)
_See current incidents from Slack._

### Tasks

Tasks are provided to regularly sync users, conversations, usergroups and channel members from Slack.

See the [available Slack tasks][firefighter.slack.tasks] that can be [scheduled from the Back-Office](../deploy/XX-tasks.md).

### Settings and configuration

See [Slack environment variables settings](../deploy/XX-settings.md#slack-integration).

#### Back-Office configuration

##### Conversations tags

You can add custom tags to Slack conversations in the back-office.

Some tags have special meaning:

- `tech_incidents`: send incidents notifications to the channel
- `dev_firefighter`: Where users can get help with the bot. Will be shown in `/incident help` for instance.
- `it_deploy`: Where the bot send notifications for deployment freezes.

## User Group Management in Back-Office

You can **add** or **import user groups** in the back-office.

!!! note "Hint"
    When adding a usergroup in the BackOffice, you can put only its ID. The rest of the information will be fetched from Slack.

### How users are invited into an incident

#### Signal Receiver for Invitations

1. **Signal Receiver**:
   - We utilize a signal receiver from the function `get_invites_from_pagerduty`, which listens for the `get_invites` signal.

2. **Adding Specific User Groups**:
   - In our example, we have set up listeners to add a specific user group when an incident is classified as a P1.

#### Handling Invitations from Slack

- The function `get_invites_from_slack` also listens for the `get_invites` signal.

- **Logic**:
  - We first check if the incident is a P1 or if it is private.
  - Then, we filter user groups tagged as `"invited_for_all_public_p1"`.
  - The function retrieves users from these groups who have a linked Slack user account, excludes the bot user, and returns a distinct set of users to be invited.

#### Aggregation of Responders

- The `build_invite_list` method in the `Incident` model sends the signal to `get_invites` to gather users from all integrations.

- **User List Aggregation**:
  - This results in a comprehensive list that aggregates users from all providers.

<!-- ##### Usergroups

You can add or import usergroups in the back-office.

First we get a signal receiver from the function `get_invites_from_pagerduty` who also listens for the `get_invites` signal.

In example, we did an listeners to add a specific users group when an incident is a P1.

The function `get_invites_from_slack` listen for the `get_invites`.

In this one, we check if the incident is P1 or not, if the incident is private.
We filter user groups tagged as "invited_for_all°public_p1", retrieves users from tese groups who have Slack user linked and excludes the bot user and return a distinct set of users to be invited.

##### Aggregation od responders

The `build_invite_list` method int the `Incident` model send the signal to `get_invites`to gather isers from all integrations.

The users list aggregates the users from all providers. -->

##### SOSes

You can configure [SOSes][firefighter.slack.models.sos.Sos] in the back-office.

## :fontawesome-brands-jira: Jira

!!! warning
    This integration is disabled by default, and is not yet documented.
    It is specific to our internal use case.
