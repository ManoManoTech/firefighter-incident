# Slack Conversation Tags Reference

This document provides a comprehensive reference of all Slack conversation tags used in the FireFighter system. Tags are used to identify and reference special Slack channels programmatically throughout the application.

## Overview

Slack conversations (channels, DMs) can be tagged with a unique identifier string to allow the application to find and interact with them programmatically. Tags are stored in the `Conversation.tag` field and must be unique across all conversations.

## Tag Categories

### Critical Incident Channels

#### `tech_incidents`
- **Channel**: `#tech-incidents` (production)
- **Purpose**: General incident announcement channel for P1-P3 critical incidents
- **Used for**:
  - Publishing incident announcements when critical incidents (P1-P3) are opened in PRD
  - Publishing updates when incidents are mitigated
  - Publishing updates when priority is escalated from P4-P5 to P1-P3
- **Conditions**: Only PRD environment, priority ≤ 3, non-private incidents
- **Code references**:
  - `slack/signals/create_incident_conversation.py:107` - Publish on incident open
  - `slack/signals/incident_updated.py:284` - Publish on incident updates
  - `incidents/tasks/updateoncall.py:92` - On-call updates
  - `pagerduty/views/oncall_trigger.py:47` - PagerDuty integration
- **First appeared**: Since early versions (0.0.15+)

#### `it_deploy`
- **Channel**: `#it-deploy` (production)
- **Purpose**: Deployment warning channel for P1 incidents affecting deployments
- **Used for**:
  - Publishing warnings when P1 incidents with deploy_warning category are created
  - Publishing warnings when incidents are escalated to P1 with deploy_warning
- **Conditions**: PRD environment, priority = 1, non-private, `incident_category.deploy_warning = True`
- **Code references**:
  - `slack/signals/create_incident_conversation.py:127` - Publish on P1 incident
  - `slack/signals/incident_updated.py:261` - Publish on priority escalation
- **First appeared**: Since early versions (0.0.15+)

#### `invited_for_all_public_p1`
- **Channel/Group**: Special Slack usergroup for P1 incident invitations
- **Purpose**: Usergroup automatically invited to all public P1 incidents
- **Used for**:
  - Automatically inviting key stakeholders to P1 incident channels
  - Ensuring visibility of critical incidents to management/leadership
- **Conditions**: Only for P1 incidents, non-private
- **Code references**:
  - `slack/signals/get_users.py:57` - Auto-invitation to P1 channels
- **First appeared**: Version 0.0.16+ (PR #110)

### RAID Alert Channels (P4-P5 Incidents)

RAID channels receive notifications for non-critical incidents (P4-P5) that don't have dedicated Slack channels. Tag format: `raid_alert__{scope}_{impact}`

#### Tag Pattern: `raid_alert__{project}_{impact}`

**Project scope**:
- `sbi` - SBI project (incidents with `project_key=SBI`)
- `incidents` - All other projects (fallback)

**Impact level**:
- `normal` - Low impact or N/A business impact
- `high` - High business impact

#### Common Tags

##### `raid_alert__sbi_normal`
- **Channel**: `#incidents` (most common for SBI)
- **Purpose**: Normal/low impact P4-P5 incidents for SBI project
- **Used for**:
  - Notifications when P4-P5 tickets are created via Landbot API
  - Business impact = "N/A", "Low", or unspecified
  - Project = SBI
- **Code references**:
  - `raid/forms.py:329` - `get_internal_alert_conversations()`
- **Broken since**: 0.0.17 (fixed in this commit)

##### `raid_alert__sbi_high`
- **Channel**: Configured channel for high-impact SBI incidents
- **Purpose**: High business impact P4-P5 incidents for SBI project
- **Used for**:
  - Notifications when P4-P5 tickets are created with high business impact
  - Business impact = "High"
  - Project = SBI
- **Code references**:
  - `raid/forms.py:329` - `get_internal_alert_conversations()`

##### `raid_alert__incidents_normal`
- **Channel**: Configured channel for non-SBI projects
- **Purpose**: Normal/low impact P4-P5 incidents for other projects
- **Used for**:
  - P4-P5 incidents from projects other than SBI
  - Business impact = "N/A", "Low", or unspecified
- **Code references**:
  - `raid/forms.py:329` - `get_internal_alert_conversations()`

##### `raid_alert__incidents_high`
- **Channel**: Configured channel for high-impact non-SBI projects
- **Purpose**: High business impact P4-P5 incidents for other projects
- **Used for**:
  - High impact P4-P5 incidents from projects other than SBI
  - Business impact = "High"
- **Code references**:
  - `raid/forms.py:329` - `get_internal_alert_conversations()`

#### Tag Pattern: `raid_alert__{domain}`

##### Example: `raid_alert__manomano.com`, `raid_alert__seller-domain.com`
- **Purpose**: Partner-specific alert channels based on reporter email domain
- **Used for**:
  - Notifications to partner-specific channels
  - Routing based on reporter's email domain (e.g., seller portals, partners)
- **Code references**:
  - `raid/forms.py:322` - `get_partner_alert_conversations()`
- **Domain extraction**: Email domain without @ symbol, without subdomains, with TLD

### Support & Development Channels

#### `dev_firefighter`
- **Channel**: FireFighter development/support channel
- **Purpose**: Support channel for FireFighter application issues
- **Used for**:
  - Error messages and support links in Slack messages
  - Help links in modals and messages
- **Code references**:
  - `slack/slack_templating.py:76` - Support links
- **First appeared**: Since early versions

## Tag Management

### Creating Tagged Channels

To create a new tagged channel in the database (via Django admin or shell):

```python
from firefighter.slack.models import Conversation

# Critical incident channel
Conversation.objects.create(
    name="tech-incidents",
    channel_id="C01234ABCDE",  # Slack channel ID
    tag="tech_incidents"
)

# RAID alert channel
Conversation.objects.create(
    name="incidents",
    channel_id="C56789FGHIJ",
    tag="raid_alert__sbi_normal"
)
```

### Tag Constraints

- **Uniqueness**: Tags must be unique across all conversations
- **Optional**: Tags can be empty string (but cannot have duplicates if set)
- **Format**: No strict format validation, but conventions exist (see patterns above)
- **Database**: Unique constraint on non-empty tags

### Finding Conversations by Tag

```python
from firefighter.slack.models import Conversation

# Exact match
channel = Conversation.objects.get_or_none(tag="tech_incidents")

# Pattern match (RAID alerts)
channels = Conversation.objects.filter(tag__contains="raid_alert__sbi")
```

## Best Practices

1. **Naming Convention**: Use descriptive, lowercase tags with underscores
2. **Documentation**: Always document new tags in this file when created
3. **Uniqueness**: Never reuse tags for different purposes
4. **Testing**: Always test tag-based logic in staging before production
5. **Migration**: When changing tags, ensure backward compatibility or plan migration

## Troubleshooting

### Channel Not Receiving Notifications

1. **Check tag exists**: Verify channel has correct tag in database
2. **Check tag format**: Ensure tag matches exact pattern (case-sensitive)
3. **Check conditions**: Verify incident/ticket meets conditions (priority, environment, etc.)
4. **Check logs**: Search logs for tag name to see if channel is being found

### Finding Which Channels Use a Tag

```sql
SELECT name, channel_id, tag
FROM slack_conversation
WHERE tag LIKE '%{search_term}%';
```

## Version History

| Version | Changes |
|---------|---------|
| 0.0.15+ | Initial tags: `tech_incidents`, `it_deploy`, `raid_alert__*` patterns |
| 0.0.16+ | Added: `invited_for_all_public_p1` usergroup tag |
| 0.0.17 | **Bug introduced**: RAID alerts stopped working due to incident linking |
| 0.0.18 | **Bug fixed**: RAID alerts restored with priority check instead of incident presence |

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
