
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

Users are invited to incidents through a system that listens for invitation requests. For critical incidents, specific user groups are automatically included in the invitation process.

The system also checks if the incident is public or private, ensuring that only the appropriate users with Slack accounts are invited. This creates a complete list of responders from all connected platforms, making sure the right people are notified.

### Custom Invitation Strategy

For users looking to create a custom invitation strategy, here’s what you need to know:

- **Django Signals**: We use Django signals to manage invitations. You can refer to the [Django signals documentation](https://docs.djangoproject.com/en/4.2/topics/signals/) for more information.


- **Registering on the Signal**: You need to register on the [`get_invites`][firefighter.incidents.signals.get_invites] signal, which provides the incident object and expects to receive a list of [`users`][firefighter.slack.models.user].

- **Signal Example**: You can check one of our [signals][firefighter.slack.signals.get_users] for a concrete example.

!!! note "Tips"
    The signal can be triggered during the creation and update of an incident.
    Invitations will only be sent once all signals have responded. It is advisable to avoid API calls and to store data in the database beforehand.

##### SOSes

You can configure [SOSes][firefighter.slack.models.sos.Sos] in the back-office.

## :fontawesome-brands-jira: Jira

### Features

Automatically create Jira tickets when FireFighter incidents are created. Each incident will generate a corresponding Jira ticket with incident details, priority, and category information.

!!! warning "Synchronization Behavior"
    **Important**: Jira integration is **unidirectional** (Impact → Jira only)

    - ✅ Impact incidents automatically create Jira tickets
    - ✅ Full P1-P5 priority mapping supported
    - ❌ Impact is NOT notified when Jira tickets are updated
    - ❌ Impact is NOT notified when Jira tickets are closed
    - ❌ No webhook from Jira back to Impact

    Manual monitoring of Jira tickets is required to track their resolution status.

### Settings and configuration

Basic configuration with environment variables (in `.env` file):

```bash
# Enable Jira integration
ENABLE_JIRA=True

# Jira API settings
RAID_JIRA_API_URL="mycompany.atlassian.local"
RAID_JIRA_API_USER="teamqraft@mycompany.local"
RAID_JIRA_API_PASSWORD="XXXXXXXXXXXXX"

# Enable RAID module (requires JIRA settings)
ENABLE_RAID=True

# RAID configuration
RAID_DEFAULT_JIRA_QRAFT_USER_ID="XXXXXXXX"
RAID_JIRA_PROJECT_KEY="T2"
RAID_TOOLBOX_URL=https://toolbox.mycompany.com/login

# Optional: Custom field for incident category
RAID_JIRA_INCIDENT_CATEGORY_FIELD="customfield_12369"
```

#### Incident Category Field

If `RAID_JIRA_INCIDENT_CATEGORY_FIELD` is configured, the incident category will be populated in the specified Jira custom field in addition to being mentioned in the ticket description.

!!! note
    Without this configuration, the incident category will only appear in the ticket description.

### Priority Mapping

FireFighter incidents are mapped to Jira tickets with corresponding priority levels:

| Impact Priority | Jira Priority | Description |
|----------------|---------------|-------------|
| P1 | 1 | Critical - System outage, complete service failure |
| P2 | 2 | High - Major functionality impaired, significant impact |
| P3 | 3 | Medium - Minor functionality affected, moderate impact |
| P4 | 4 | Low - Small issues, minimal impact |
| P5 | 5 | Lowest - Cosmetic issues, enhancement requests |

!!! info "Priority Fallback"
    If an incident has an invalid priority value (outside P1-P5 range), it will automatically fallback to **P1 (Critical)** in Jira to ensure proper escalation.

### Ticket Information

Each Jira ticket created from a FireFighter incident includes:

- **Summary**: Incident title
- **Description**: Incident description with:
  - Incident category and group information
  - Priority level with emoji indicator
  - Links to Slack conversation and FireFighter incident page
- **Priority**: Mapped from P1-P5 as described above
- **Reporter**: The user who created the incident (with fallback to default user)
- **Labels**: Custom labels if configured
- **Custom Fields**: Incident category (if custom field is configured)
