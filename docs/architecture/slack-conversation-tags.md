# Slack Conversation Tags Reference

This document provides a comprehensive reference of all Slack conversation tags used in the FireFighter system. Tags are used to identify and reference special Slack channels programmatically throughout the application.

## Overview

Slack conversations (channels, DMs) can be tagged with a unique identifier string to allow the application to find and interact with them programmatically. Tags are stored in the `Conversation.tag` field and must be unique across all conversations.

## Tag Categories

### Critical Incident Channels

#### `tech_incidents`
- **Purpose**: General incident announcement channel for P1-P3 critical incidents
- **Used for**:
  - Publishing incident announcements when critical incidents (P1-P3) are opened in production environment
  - Publishing updates when incidents are mitigated
  - Publishing updates when priority is escalated from P4-P5 to P1-P3
- **Conditions**: Only production environment, priority ≤ 3, non-private incidents
- **Code references**:
  - `slack/signals/create_incident_conversation.py:107` - Publish on incident open
  - `slack/signals/incident_updated.py:284` - Publish on incident updates
  - `incidents/tasks/updateoncall.py:92` - On-call updates
  - `pagerduty/views/oncall_trigger.py:47` - PagerDuty integration

#### `it_deploy`
- **Purpose**: Deployment warning channel for P1 incidents affecting deployments
- **Used for**:
  - Publishing warnings when P1 incidents with `deploy_warning` category are created
  - Publishing warnings when incidents are escalated to P1 with `deploy_warning`
- **Conditions**: Production environment, priority = 1, non-private, `incident_category.deploy_warning = True`
- **Code references**:
  - `slack/signals/create_incident_conversation.py:127` - Publish on P1 incident
  - `slack/signals/incident_updated.py:261` - Publish on priority escalation

#### `invited_for_all_public_p1`
- **Purpose**: Slack usergroup automatically invited to all public P1 incidents
- **Used for**:
  - Automatically inviting key stakeholders to P1 incident channels
  - Ensuring visibility of critical incidents to management/leadership
- **Conditions**: Only for P1 incidents, non-private
- **Code references**:
  - `slack/signals/get_users.py:57` - Auto-invitation to P1 channels

### RAID Alert Channels (P4-P5 Incidents)

RAID channels receive notifications for non-critical incidents (P4-P5) that don't have dedicated Slack channels.

#### Tag Pattern: `raid_alert__{project}_{impact}`

This pattern allows routing P4-P5 incidents to different channels based on project and business impact.

**Project scope**:
- Use your Jira project keys (lowercase) to create project-specific channels
- Use a generic fallback project name (e.g., `incidents`) for all other projects

**Impact level**:
- `normal` - Low impact or N/A business impact
- `high` - High business impact

**Examples**:
- `raid_alert__myproject_normal` - Normal impact incidents for "MyProject" Jira project
- `raid_alert__myproject_high` - High impact incidents for "MyProject" Jira project
- `raid_alert__incidents_normal` - Normal impact incidents for all other projects
- `raid_alert__incidents_high` - High impact incidents for all other projects

**Code references**:
- `raid/forms.py:329` - `get_internal_alert_conversations()`

**How it works**:
```python
# The system builds tags dynamically:
# - If jira_ticket.project_key matches your configured project: use project key
# - Otherwise: use "incidents" as fallback
# - If business_impact == "High": use "high", otherwise "normal"
```

#### Tag Pattern: `raid_alert__{domain}`

Partner-specific alert channels based on reporter email domain.

**Purpose**: Route notifications to partner or customer-specific channels

**Examples**:
- `raid_alert__partner-company.com` - Alerts for incidents reported by users @partner-company.com
- `raid_alert__customer-domain.com` - Alerts for incidents reported by users @customer-domain.com

**Code references**:
- `raid/forms.py:322` - `get_partner_alert_conversations()`

**Domain extraction**: Email domain without @ symbol, without subdomains, with TLD (e.g., `user@subdomain.example.com` → `example.com`)

### Support & Development Channels

#### `dev_firefighter`
- **Purpose**: Support channel for FireFighter application issues
- **Used for**:
  - Error messages and support links in Slack messages
  - Help links in modals and messages
- **Code references**:
  - `slack/slack_templating.py:76` - Support links

## Tag Management

### Creating Tagged Channels

To create a new tagged channel in the database (via Django admin or shell):

```python
from firefighter.slack.models import Conversation

# Critical incident channel
Conversation.objects.create(
    name="your-incidents-channel",
    channel_id="C01234ABCDE",  # Get this from Slack (right-click channel > View channel details)
    tag="tech_incidents"
)

# RAID alert channel for a specific project
Conversation.objects.create(
    name="your-project-alerts",
    channel_id="C56789FGHIJ",
    tag="raid_alert__yourproject_normal"
)

# Partner-specific channel
Conversation.objects.create(
    name="partner-alerts",
    channel_id="C99999ZZZZZ",
    tag="raid_alert__partner-domain.com"
)
```

### Tag Constraints

- **Uniqueness**: Tags must be unique across all conversations
- **Optional**: Tags can be empty string (but cannot have duplicates if set)
- **Format**: No strict format validation, but conventions exist (see patterns above)
- **Database**: Unique constraint on non-empty tags
- **Case-sensitive**: `tech_incidents` ≠ `TECH_INCIDENTS`

### Finding Conversations by Tag

```python
from firefighter.slack.models import Conversation

# Exact match
channel = Conversation.objects.get_or_none(tag="tech_incidents")

# Pattern match (RAID alerts for a specific project)
channels = Conversation.objects.filter(tag__contains="raid_alert__myproject")
```

## Configuration Guide

### Step 1: Identify Your Needs

1. **Critical incidents channel** - Where should P1-P3 incidents be announced?
   - Create a Slack channel (e.g., `#incidents`, `#critical-alerts`)
   - Tag it with `tech_incidents`

2. **Deployment warnings** (optional) - Where should P1 incidents affecting deployments be announced?
   - Create a Slack channel (e.g., `#deployments`, `#deploy-freeze`)
   - Tag it with `it_deploy`

3. **P1 leadership usergroup** (optional) - Who should be automatically invited to P1 incidents?
   - Create a Slack usergroup (e.g., `@incident-responders`, `@leadership`)
   - Tag it with `invited_for_all_public_p1`

4. **P4-P5 alerts** - Where should non-critical incidents be posted?
   - Create channels per project and impact level
   - Tag with `raid_alert__{project}_{impact}` pattern

5. **Support channel** - Where should FireFighter errors be reported?
   - Create a Slack channel (e.g., `#firefighter-support`)
   - Tag it with `dev_firefighter`

### Step 2: Create Channels in Slack

Create the channels you identified above in your Slack workspace.

### Step 3: Get Channel IDs

For each channel:
1. Right-click the channel in Slack
2. Select "View channel details"
3. Scroll to the bottom - the Channel ID is shown there (format: `C01234ABCDE`)

### Step 4: Create Database Entries

Use Django admin or shell to create `Conversation` objects with the appropriate tags.

## Best Practices

1. **Naming Convention**: Use descriptive, lowercase tags with underscores
2. **Documentation**: Document your organization's tag configuration
3. **Uniqueness**: Never reuse tags for different purposes
4. **Testing**: Always test tag-based logic in staging before production
5. **Migration**: When changing tags, ensure backward compatibility or plan migration
6. **Access Control**: Ensure channels have appropriate visibility in Slack

## Troubleshooting

### Channel Not Receiving Notifications

1. **Check tag exists**: Verify channel has correct tag in database
   ```python
   from firefighter.slack.models import Conversation
   Conversation.objects.filter(tag="tech_incidents")
   ```

2. **Check tag format**: Ensure tag matches exact pattern (case-sensitive)

3. **Check conditions**: Verify incident/ticket meets conditions (priority, environment, etc.)

4. **Check logs**: Search application logs for tag name to see if channel is being found

5. **Check Slack permissions**: Ensure FireFighter bot is a member of the channel

### Finding Which Channels Use a Tag

```sql
SELECT name, channel_id, tag
FROM slack_conversation
WHERE tag LIKE '%{search_term}%';
```

```python
# Or via Django ORM
from firefighter.slack.models import Conversation
Conversation.objects.filter(tag__icontains="raid_alert")
```

## Related Documentation

- [JIRA Integration](jira-integration.md)
- [Incident Workflow](incident-workflows.md)

## Code References

### Key Files

- `slack/models/conversation.py` - Conversation model with tag field
- `slack/signals/create_incident_conversation.py` - Incident channel creation and announcements
- `slack/signals/incident_updated.py` - Incident update notifications
- `raid/forms.py` - RAID alert logic (P4-P5 incidents)
- `slack/rules.py` - Rules for publishing in general channels

### Database Schema

```sql
CREATE TABLE slack_conversation (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80),
    channel_id VARCHAR(80) UNIQUE,
    tag VARCHAR(80),  -- Unique constraint when not empty
    -- ... other fields
    CONSTRAINT unique__tag UNIQUE (tag) WHERE tag != ''
);
```

## Example Configurations

### Minimal Setup

```python
# P1-P3 incidents
Conversation.objects.create(name="incidents", channel_id="C001", tag="tech_incidents")

# P4-P5 incidents
Conversation.objects.create(name="tickets", channel_id="C002", tag="raid_alert__incidents_normal")
```

### Complete Setup

```python
# Critical incidents
Conversation.objects.create(name="incidents", channel_id="C001", tag="tech_incidents")
Conversation.objects.create(name="deploy-freeze", channel_id="C002", tag="it_deploy")

# Leadership usergroup
Conversation.objects.create(name="incident-leads", channel_id="S001", tag="invited_for_all_public_p1")

# P4-P5 by project and impact
Conversation.objects.create(name="platform-alerts", channel_id="C003", tag="raid_alert__platform_normal")
Conversation.objects.create(name="platform-urgent", channel_id="C004", tag="raid_alert__platform_high")
Conversation.objects.create(name="general-alerts", channel_id="C005", tag="raid_alert__incidents_normal")

# Partner channels
Conversation.objects.create(name="partner-x-alerts", channel_id="C006", tag="raid_alert__partner-x.com")

# Support
Conversation.objects.create(name="firefighter-support", channel_id="C007", tag="dev_firefighter")
```
