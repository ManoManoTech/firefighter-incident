# Slack Conversation Tags Reference

This document provides a comprehensive reference of the Slack conversation tag system used in FireFighter. Tags are used to identify and reference special Slack channels programmatically throughout the application.

## Overview

Slack conversations (channels, DMs, usergroups) can be tagged with a unique identifier string to allow the application to find and interact with them programmatically. Tags are stored in the `Conversation.tag` field and must be unique across all conversations.

## How Tags Work

The tag system allows FireFighter to:
1. Find specific channels without hardcoding Slack channel IDs
2. Route notifications to the appropriate channels based on incident properties
3. Support different channel configurations across organizations
4. Maintain flexibility when channels are renamed or reorganized in Slack

## Tag Reference

### Critical Incident Tags

#### `tech_incidents`

**Purpose**: General incident announcement channel for P1-P3 critical incidents

**When notifications are sent**:
- Critical incidents (P1-P3) are opened in production environment
- Incidents are mitigated
- Priority is escalated from P4-P5 to P1-P3

**Conditions**: Only production environment, priority ≤ 3, non-private incidents

**Code references**:
- `slack/signals/create_incident_conversation.py:107` - Publish on incident open
- `slack/signals/incident_updated.py:284` - Publish on incident updates
- `incidents/tasks/updateoncall.py:92` - On-call updates
- `pagerduty/views/oncall_trigger.py:47` - PagerDuty integration

#### `it_deploy`

**Purpose**: Deployment warning channel for P1 incidents affecting deployments

**When notifications are sent**:
- P1 incidents with `deploy_warning` category are created
- Incidents are escalated to P1 with `deploy_warning`

**Conditions**: Production environment, priority = 1, non-private, `incident_category.deploy_warning = True`

**Code references**:
- `slack/signals/create_incident_conversation.py:127` - Publish on P1 incident
- `slack/signals/incident_updated.py:261` - Publish on priority escalation

#### `invited_for_all_public_p1`

**Purpose**: Slack usergroup automatically invited to all public P1 incidents

**When used**:
- Automatically inviting key stakeholders to P1 incident channels
- Ensuring visibility of critical incidents to management/leadership

**Conditions**: Only for P1 incidents, non-private

**Code references**:
- `slack/signals/get_users.py:57` - Auto-invitation to P1 channels

**Note**: This should be a Slack usergroup ID (starting with "S"), not a channel

### RAID Alert Tags (P4-P5 Incidents)

RAID channels receive notifications for non-critical incidents (P4-P5) that don't have dedicated Slack channels.

#### Tag Pattern: `raid_alert__{project}_{impact}`

This pattern allows routing P4-P5 incidents to different channels based on Jira project and business impact.

**Pattern components**:
- `{project}` - Your Jira project key in lowercase (e.g., if you have a Jira project "PLATFORM", use "platform")
- `{impact}` - Either "normal" (for low/N/A impact) or "high" (for high impact)

**How it works**:
```python
# The system builds tags dynamically based on:
# 1. Jira project key (lowercase)
# 2. Business impact level

# Examples:
# - Project "PLATFORM", impact "N/A"  → raid_alert__platform_normal
# - Project "PLATFORM", impact "High" → raid_alert__platform_high
# - Project "API", impact "Low"       → raid_alert__api_normal
# - Fallback project, impact "High"   → raid_alert__incidents_high
```

**Code references**:
- `raid/forms.py:329` - `get_internal_alert_conversations()`

**Configuration tip**: Create a fallback using `incidents` as the project name for any Jira projects that don't have dedicated channels.

#### Tag Pattern: `raid_alert__{domain}`

Partner-specific alert channels based on reporter email domain.

**Purpose**: Route notifications to partner or customer-specific channels

**How it works**:
- Extracts domain from reporter's email
- Removes @ symbol and subdomains
- Keeps TLD (e.g., `user@subdomain.example.com` → `example.com`)
- Looks for channel with tag `raid_alert__example.com`

**Code references**:
- `raid/forms.py:322` - `get_partner_alert_conversations()`

### Support Tag

#### `dev_firefighter`

**Purpose**: Support channel for FireFighter application issues

**When used**:
- Error messages and support links in Slack messages
- Help links in modals and messages

**Code references**:
- `slack/slack_templating.py:76` - Support links

## Configuration Guide

### Step 1: Plan Your Channels

Decide which Slack channels you need based on your organization's requirements:

1. **Critical incidents** - Required tag: `tech_incidents`
   - Use case: Announce all P1-P3 critical incidents

2. **Deployment warnings** - Optional tag: `it_deploy`
   - Use case: Warn about P1 incidents affecting deployments

3. **P1 leadership notification** - Optional tag: `invited_for_all_public_p1`
   - Use case: Auto-invite executives/leadership to P1 incidents
   - This should be a Slack usergroup, not a channel

4. **P4-P5 alerts** - Tags: `raid_alert__{project}_{impact}`
   - Use case: Route non-critical incidents by project and severity
   - You'll need multiple channels for different projects/impact levels

5. **Partner alerts** - Optional tags: `raid_alert__{domain}`
   - Use case: Route incidents to partner-specific channels

6. **Support** - Optional tag: `dev_firefighter`
   - Use case: FireFighter application support and errors

### Step 2: Create Channels in Slack

Create the channels and usergroups you identified in your Slack workspace.

### Step 3: Get Slack IDs

For each channel or usergroup:
1. Right-click the channel/usergroup in Slack
2. Select "View channel details" (or "View user group details")
3. The ID is shown at the bottom
   - Channels start with `C` (e.g., `C01234ABCDE`)
   - Usergroups start with `S` (e.g., `S98765ZYXWV`)

### Step 4: Create Conversation Objects

Use Django admin or shell to create `Conversation` objects linking Slack IDs to tags:

```python
from firefighter.slack.models import Conversation

# Example: Critical incidents channel
Conversation.objects.create(
    name="<your-channel-name>",  # Descriptive name for reference
    channel_id="C01234ABCDE",    # Slack channel ID from step 3
    tag="tech_incidents"          # Tag from documentation above
)

# Example: RAID alert for a specific Jira project
Conversation.objects.create(
    name="<your-channel-name>",
    channel_id="C56789FGHIJ",
    tag="raid_alert__yourproject_normal"  # Replace 'yourproject' with your Jira project key (lowercase)
)

# Example: Partner-specific channel
Conversation.objects.create(
    name="<your-channel-name>",
    channel_id="C99999ZZZZZ",
    tag="raid_alert__partner-domain.com"  # Replace with actual domain
)

# Example: P1 leadership usergroup
Conversation.objects.create(
    name="<your-usergroup-name>",
    channel_id="S98765ZYXWV",     # Note: Usergroup ID starts with 'S'
    tag="invited_for_all_public_p1"
)
```

## Tag Constraints

- **Uniqueness**: Tags must be unique across all conversations
- **Optional**: Tags can be empty string (multiple channels can have no tag)
- **Format**: No strict format validation, but follow conventions documented above
- **Database**: Unique constraint on non-empty tags
- **Case-sensitive**: `tech_incidents` ≠ `TECH_INCIDENTS`

## Querying by Tag

```python
from firefighter.slack.models import Conversation

# Find a specific channel by tag
channel = Conversation.objects.get_or_none(tag="tech_incidents")

# Find all RAID alert channels for a project
channels = Conversation.objects.filter(tag__contains="raid_alert__myproject")

# Check if a tag is configured
if Conversation.objects.filter(tag="it_deploy").exists():
    print("Deployment warnings are configured")
```

## Best Practices

1. **Document your configuration** - Keep a record of which tags map to which channels
2. **Use descriptive channel names** - Make it easy to identify channel purpose
3. **Test in staging first** - Verify tag-based routing before production
4. **Never reuse tags** - Each tag should have one purpose only
5. **Plan for growth** - Consider future projects when designing tag structure
6. **Maintain consistency** - Use the same tag patterns across your organization

## Troubleshooting

### Channel Not Receiving Notifications

1. **Verify tag exists in database**:
   ```python
   from firefighter.slack.models import Conversation
   Conversation.objects.filter(tag="tech_incidents")
   ```

2. **Check tag matches exactly** (case-sensitive):
   - `tech_incidents` ✅
   - `Tech_Incidents` ❌

3. **Verify incident meets conditions**:
   - For `tech_incidents`: Check priority ≤ 3, production environment, non-private
   - For `raid_alert__*`: Check project key matches, business impact level

4. **Check application logs** for tag resolution messages

5. **Verify bot permissions**:
   - Ensure FireFighter bot is a member of the channel
   - Check bot has necessary Slack scopes

### Finding All Tagged Channels

```sql
SELECT name, channel_id, tag
FROM slack_conversation
WHERE tag IS NOT NULL AND tag != ''
ORDER BY tag;
```

Or via Django ORM:
```python
from firefighter.slack.models import Conversation
tagged_channels = Conversation.objects.exclude(tag="").order_by("tag")
for conv in tagged_channels:
    print(f"{conv.tag:40} → {conv.name} ({conv.channel_id})")
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

## Tag Reference Summary

| Tag | Type | Purpose |
|-----|------|---------|
| `tech_incidents` | Channel | P1-P3 critical incident announcements |
| `it_deploy` | Channel | P1 deployment warnings |
| `invited_for_all_public_p1` | Usergroup | Auto-invite to P1 incidents |
| `raid_alert__{project}_normal` | Channel | P4-P5 normal impact alerts by project |
| `raid_alert__{project}_high` | Channel | P4-P5 high impact alerts by project |
| `raid_alert__{domain}` | Channel | Partner/customer-specific alerts |
| `dev_firefighter` | Channel | FireFighter support and errors |

Replace `{project}` with your Jira project key (lowercase) and `{domain}` with email domains.
