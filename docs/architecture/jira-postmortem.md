# Jira Post-mortem Integration

**Status**: ✅ Implemented (v0.0.21+)
**Related PR**: [#184](https://github.com/ManoManoTech/firefighter-incident/pull/184)

---

## Quick Start

### Flow

FireFighter can create Jira post-mortems in addition to (or instead of) Confluence pages.

**At a glance**:
1. User clicks **Create post-mortem** in Slack.
2. Jira issue is created with templated content.
3. Incident commander is auto-assigned when they have a Jira account.
4. Slack notification posts back to the incident channel.

### Architecture (high level)

```
Slack Modal → PostMortemManager → {Confluence Service | JiraPostMortemService}
                              ↳ Create issue → Assign → Notify → Persist
```

### Configuration essentials

#### Required

```bash
ENABLE_JIRA_POSTMORTEM=true
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT
JIRA_POSTMORTEM_ISSUE_TYPE="Post-mortem"
```

#### Custom field IDs (optional overrides)

```bash
JIRA_FIELD_INCIDENT_SUMMARY=customfield_12699
JIRA_FIELD_TIMELINE=customfield_12700
JIRA_FIELD_ROOT_CAUSES=customfield_12701
JIRA_FIELD_IMPACT=customfield_12702
JIRA_FIELD_MITIGATION_ACTIONS=customfield_12703
JIRA_FIELD_INCIDENT_CATEGORY=customfield_12369
```

### Deployment modes at a glance

| Mode | Config | Behavior |
|------|--------|----------|
| **Confluence only** | `ENABLE_CONFLUENCE=true`, `ENABLE_JIRA_POSTMORTEM=false` | Legacy (Confluence only) |
| **Jira only** | `ENABLE_CONFLUENCE=false`, `ENABLE_JIRA_POSTMORTEM=true` | Target (Jira only) |
| **Dual mode** | Both enabled | Migration (both backends) |

### Pre-populated fields (cheat sheet)

| Field | Content |
|-------|---------|
| **Incident Summary** | Channel link, priority, status, created date, description |
| **Timeline** | Created time + key events (with TODO markers) |
| **Impact** | Affected systems + duration (with TODO markers) |
| **Mitigation Actions** | Related Jira follow-up links (with TODO markers) |
| **Root Causes** | Placeholder (completed during retrospective) |

### Feature highlights

```
User submits → Validate → Create issue → Assign → Notify → Persist
```

- **Automatic creation**: Uses Django templates rendered in Jira Wiki markup.
- **Commander assignment**: Auto-assigns when `incident.roles_set` has a commander with `user.jira_user`; logs warnings on failure.
- **Slack notifications**: Posts confirmation back to the incident channel (failure only logs an error).

### Troubleshooting cheat sheet

| Problem | Cause | Quick fix |
|---------|-------|-----------|
| Silent creation failure | Both backends disabled or bad credentials | Verify env vars and logs |
| Commander not assigned | No linked Jira account | Link Jira account for commander |
| Slack notification missing | No Slack conversation or bot missing | Ensure bot is in the channel |
| Wiki markup not rendering | Field renderer not Wiki style | Set Jira renderer to "Wiki Style Renderer" |

### Implementation pointers

- `src/firefighter/jira_app/models.py` – `JiraPostMortem`
- `src/firefighter/jira_app/service_postmortem.py` – `JiraPostMortemService`
- `src/firefighter/jira_app/templates/jira/postmortem/` – Jira Wiki templates
- `src/firefighter/confluence/models.py` – `PostMortemManager`

### Related quick links

- [Jira Integration](jira-integration.md)
- [Incident Workflow](incident-workflow.md)
- [Architecture Overview](overview.md)

---

## Overview

FireFighter supports creating post-mortems in Jira as an alternative to (or in addition to) Confluence. This feature allows teams to:

- Create structured post-mortem tickets in Jira
- Automatically assign post-mortems to incident commanders
- Send Slack notifications with direct links to Jira tickets
- Support flexible deployment modes (Confluence only, Jira only, or both)

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Slack Modal                              │
│  (User clicks "Create Post-mortem")                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              PostMortemManager                               │
│  (Orchestrates creation on enabled backends)                │
└─────────────┬───────────────────────────┬───────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────┐  ┌──────────────────────────────┐
│ Confluence Service      │  │ JiraPostMortemService        │
│ (existing)              │  │ (new)                        │
└─────────────────────────┘  └──────────────┬───────────────┘
                                            │
                             ┌──────────────┼──────────────┐
                             ▼              ▼              ▼
                    ┌────────────┐  ┌──────────┐  ┌──────────┐
                    │ Create     │  │ Assign   │  │ Notify   │
                    │ Jira Issue │  │ to       │  │ Slack    │
                    │            │  │ Commander│  │ Channel  │
                    └────────────┘  └──────────┘  └──────────┘
```

### Database Schema

```sql
CREATE TABLE jira_postmortem (
    id BIGSERIAL PRIMARY KEY,
    incident_id INTEGER NOT NULL UNIQUE,  -- OneToOne with incidents_incident
    jira_issue_key VARCHAR(32) NOT NULL UNIQUE,  -- e.g., "INCIDENT-123"
    jira_issue_id VARCHAR(32) NOT NULL UNIQUE,   -- Jira internal ID
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    created_by_id UUID,  -- FK to users (nullable)

    FOREIGN KEY (incident_id) REFERENCES incidents_incident(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
);
```

### Models

#### JiraPostMortem

**File**: `src/firefighter/jira_app/models.py`

```python
class JiraPostMortem(models.Model):
    """Jira Post-mortem linked to an Incident."""

    incident = models.OneToOneField(
        "incidents.Incident",
        on_delete=models.CASCADE,
        related_name="jira_postmortem_for",
    )
    jira_issue_key = models.CharField(max_length=32, unique=True)
    jira_issue_id = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    @property
    def issue_url(self) -> str:
        """Return Jira issue URL."""
        return f"{settings.RAID_JIRA_API_URL}/browse/{self.jira_issue_key}"
```

**Usage**:

```python
# Check if incident has Jira post-mortem
if hasattr(incident, "jira_postmortem_for"):
    jira_pm = incident.jira_postmortem_for
    print(f"Jira post-mortem: {jira_pm.issue_url}")

# Access from JiraPostMortem side
jira_pm = JiraPostMortem.objects.get(jira_issue_key="INCIDENT-123")
incident = jira_pm.incident
```

## Configuration

### Environment Variables

**Required** (if `ENABLE_JIRA_POSTMORTEM=true`):

```bash
# Enable Jira post-mortem feature
ENABLE_JIRA_POSTMORTEM=true

# Jira project configuration
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT        # Project where post-mortems are created
JIRA_POSTMORTEM_ISSUE_TYPE=Post-mortem      # Issue type name
```

**Optional** (custom field IDs):

```bash
# Jira custom field IDs (defaults shown)
JIRA_FIELD_INCIDENT_SUMMARY=customfield_12699
JIRA_FIELD_TIMELINE=customfield_12700
JIRA_FIELD_ROOT_CAUSES=customfield_12701
JIRA_FIELD_IMPACT=customfield_12702
JIRA_FIELD_MITIGATION_ACTIONS=customfield_12703
JIRA_FIELD_INCIDENT_CATEGORY=customfield_12369
```

### Deployment Modes

FireFighter supports three deployment modes:

| Mode | `ENABLE_CONFLUENCE` | `ENABLE_JIRA_POSTMORTEM` | Behavior |
|------|---------------------|--------------------------|----------|
| **Confluence only** (legacy) | `true` | `false` | Creates post-mortems only in Confluence |
| **Jira only** | `false` | `true` | Creates post-mortems only in Jira |
| **Dual mode** (migration) | `true` | `true` | Creates post-mortems in **both** Confluence and Jira |

**Example configurations**:

```bash
# Confluence only (existing behavior)
ENABLE_CONFLUENCE=true
ENABLE_JIRA_POSTMORTEM=false

# Dual mode (for testing/migration)
ENABLE_CONFLUENCE=true
ENABLE_JIRA_POSTMORTEM=true
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT

# Jira only (target state)
ENABLE_CONFLUENCE=false
ENABLE_JIRA_POSTMORTEM=true
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT
```

## Features

### 1. Automatic Post-mortem Creation

When a user clicks "Create post-mortem" in Slack:

1. **Validation**: Check if post-mortem already exists (Confluence and/or Jira)
2. **Creation**: Create Jira issue with pre-populated fields using templates
3. **Assignment**: Auto-assign ticket to incident commander (if commander has `jira_user`)
4. **Notification**: Send Slack message to incident channel with link to ticket
5. **Database**: Create `JiraPostMortem` record linked to incident

**Error Handling**:
- Commander assignment failure → Log warning, continue
- Slack notification failure → Log error, continue
- Jira API failure → Raise exception, rollback

### 2. Jira Issue Templates

Post-mortem tickets are created with 5 custom fields using **Jira Wiki Markup** format:

#### Incident Summary (`customfield_12699`)

Pre-populated with:
- Incident Slack channel link
- Priority (P1-P5)
- Status
- Created date
- Description (if available)
- Affected components (if available)

**Example**:
```
h2. Incident Summary

*Incident:* [#20250101-abcd1234|https://slack.com/...]
*Priority:* P1 (P1)
*Status:* Closed
*Created:* 2025-01-01 14:30 UTC

h3. Description

Database replica lag causing timeouts
```

#### Timeline (`customfield_12700`)

Pre-populated with:
- Incident creation time
- Key events from incident updates

**Note**: Includes TODO placeholder for users to complete manually.

#### Impact (`customfield_12702`)

Pre-populated with:
- Affected systems/components
- Incident duration (opened, closed, total)

**Note**: Includes TODO placeholders for user impact and business impact.

#### Mitigation Actions (`customfield_12703`)

Pre-populated with:
- Link to related Jira follow-up ticket (if exists)

**Note**: Includes TODO placeholders for immediate and long-term actions.

#### Root Causes (`customfield_12701`)

**Note**: Fully TODO - users complete during retrospective.

#### Incident Category (`customfield_12369`)

Auto-populated from `incident.incident_category.name`.

### 3. Commander Assignment

If the incident has a commander with a linked Jira account (`user.jira_user`):

```python
commander = incident.roles_set.filter(role_type__slug="commander").first()
if commander and hasattr(commander.user, "jira_user"):
    jira_client.assign_issue(
        issue_key=jira_issue["key"],
        account_id=commander.user.jira_user.id
    )
```

**Graceful failure**: If assignment fails (no Jira account, API error), a warning is logged but post-mortem creation continues.

### 4. Slack Notifications

After successful creation, a message is sent to the incident channel:

```
📝 Post-mortem created for incident #123

Jira ticket: INCIDENT-456
Assigned to: John Doe

Please complete the post-mortem analysis with details from the incident retrospective.
```

**Graceful failure**: If notification fails, an error is logged but post-mortem creation continues.

### 5. Slack Modal Integration

The post-mortem modal shows different states based on what exists:

**No post-mortem exists**:
```
Post-mortem does not yet exist for incident #123.
Click the button to create post-mortem on Confluence and Jira.

[Create postmortem]
```

**Post-mortem(s) already exist**:
```
Post-mortem(s) for incident #123 already exist:
• Confluence: View page
• Jira: INCIDENT-456
```

**Disabled**:
```
❌ Post-mortem creation is currently disabled.
```

## API Reference

### JiraPostMortemService

**File**: `src/firefighter/jira_app/service_postmortem.py`

#### `create_postmortem_for_incident(incident, created_by=None)`

Creates a Jira post-mortem for an incident.

**Parameters**:
- `incident` (Incident): Incident to create post-mortem for
- `created_by` (User, optional): User creating the post-mortem

**Returns**: `JiraPostMortem` instance

**Raises**:
- `ValueError`: If incident already has a Jira post-mortem
- `JiraAPIError`: If Jira API call fails

**Example**:
```python
from firefighter.jira_app.service_postmortem import jira_postmortem_service

jira_pm = jira_postmortem_service.create_postmortem_for_incident(
    incident=incident,
    created_by=request.user
)

print(f"Created: {jira_pm.issue_url}")
```

### PostMortemManager

**File**: `src/firefighter/confluence/models.py`

#### `create_postmortem_for_incident(incident)`

Creates post-mortem(s) for incident based on feature flags.

**Parameters**:
- `incident` (Incident): Incident to create post-mortem(s) for

**Returns**: `tuple[PostMortem | None, JiraPostMortem | None]`
- First element: Confluence post-mortem (or None)
- Second element: Jira post-mortem (or None)

**Raises**:
- `ValueError`: If both backends are disabled or post-mortem already exists

**Example**:
```python
from firefighter.confluence.models import PostMortem

confluence_pm, jira_pm = PostMortem.objects.create_postmortem_for_incident(incident)

if confluence_pm:
    print(f"Confluence: {confluence_pm.page_url}")
if jira_pm:
    print(f"Jira: {jira_pm.issue_url}")
```

### JiraClient Extensions

**File**: `src/firefighter/jira_app/client.py`

#### `create_issue(project_key, issue_type, fields)`

Creates a Jira issue with custom fields.

**Parameters**:
- `project_key` (str): Jira project key (e.g., "INCIDENT")
- `issue_type` (str): Issue type name (e.g., "Post-mortem")
- `fields` (dict): Dictionary of field IDs to values

**Returns**: `dict` with `key` and `id` of created issue

**Raises**: `JiraAPIError` if creation fails

**Example**:
```python
from firefighter.jira_app.client import JiraClient

client = JiraClient()
issue = client.create_issue(
    project_key="INCIDENT",
    issue_type="Post-mortem",
    fields={
        "summary": "Post-mortem for #incident-123",
        "customfield_12699": "Incident summary content...",
    }
)

print(f"Created: {issue['key']}")  # "INCIDENT-456"
```

#### `assign_issue(issue_key, account_id)`

Assigns a Jira issue to a user.

**Parameters**:
- `issue_key` (str): Jira issue key (e.g., "INCIDENT-123")
- `account_id` (str): Jira account ID of the user

**Raises**: `JiraAPIError` if assignment fails

**Example**:
```python
client.assign_issue(
    issue_key="INCIDENT-456",
    account_id=user.jira_user.id
)
```

## Migration Guide

### Step 1: Verify Configuration

Ensure Jira is properly configured:

```bash
# Check existing Jira configuration
ENABLE_JIRA=true
RAID_JIRA_API_USER=service-account@example.com
RAID_JIRA_API_PASSWORD=***
RAID_JIRA_API_URL=https://jira.example.com
```

### Step 2: Configure Custom Fields

Query Jira API to get custom field IDs for your "Post-mortem" issue type:

```bash
curl -u user:token "https://jira.example.com/rest/api/2/issue/createmeta?projectKeys=INCIDENT&issuetypeNames=Post-mortem&expand=projects.issuetypes.fields"
```

Update environment variables with correct field IDs.

### Step 3: Enable Dual Mode

Deploy with both backends enabled for testing:

```bash
ENABLE_CONFLUENCE=true
ENABLE_JIRA_POSTMORTEM=true
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT
JIRA_POSTMORTEM_ISSUE_TYPE=Post-mortem
```

### Step 4: Test Creation

1. Create a test incident (P1 or P2 that requires post-mortem)
2. Click "Create post-mortem" in Slack
3. Verify:
   - ✅ Confluence page created
   - ✅ Jira ticket created
   - ✅ Commander assigned in Jira
   - ✅ Slack notification received
   - ✅ Both links visible in modal

### Step 5: Monitor & Adjust

Monitor logs for warnings/errors:

```bash
# Check for assignment failures
grep "Failed to assign post-mortem to commander" logs/app.log

# Check for notification failures
grep "Failed to send Slack notification for post-mortem" logs/app.log

# Check for Jira API errors
grep "JiraAPIError" logs/app.log
```

### Step 6: Switch to Jira-only

Once confident, disable Confluence:

```bash
ENABLE_CONFLUENCE=false
ENABLE_JIRA_POSTMORTEM=true
```

## Troubleshooting

### Post-mortem creation fails silently

**Symptoms**: Modal closes but no post-mortem created, no error shown.

**Causes**:
- Both `ENABLE_CONFLUENCE` and `ENABLE_JIRA_POSTMORTEM` are `false`
- Jira API credentials invalid

**Solutions**:
1. Check logs for error messages
2. Verify environment variables are set correctly
3. Test Jira API connectivity manually

### Commander not assigned

**Symptoms**: Post-mortem created but not assigned to anyone.

**Causes**:
- Commander has no linked Jira account (`user.jira_user` is None)
- Jira account ID is invalid
- Insufficient permissions for service account

**Solutions**:
1. Check if user has Jira account: `python manage.py shell -c "from firefighter.incidents.models import User; u = User.objects.get(username='commander'); print(hasattr(u, 'jira_user'))"`
2. Check logs for assignment warnings
3. Verify service account has "Assign Issues" permission in Jira

### Slack notification not sent

**Symptoms**: Post-mortem created and assigned but no Slack message.

**Causes**:
- Incident has no Slack conversation (`hasattr(incident, 'conversation')` is False)
- Slack API error
- Bot not in channel

**Solutions**:
1. Check if incident has conversation: `python manage.py shell -c "from firefighter.incidents.models import Incident; i = Incident.objects.get(id=123); print(hasattr(i, 'conversation'))"`
2. Check logs for notification errors
3. Verify bot is member of incident channel

### Wiki Markup not rendering correctly

**Symptoms**: Templates display as plain text instead of formatted in Jira.

**Causes**:
- Custom field type is not "Text Field (multi-line)" in Jira
- Field renderer is set to "Plain text" instead of "Wiki Style Renderer"

**Solutions**:
1. Go to Jira → Settings → Issues → Custom Fields
2. Find the custom field (e.g., "Incident Summary")
3. Click "Configure" → "Edit Field Configuration"
4. Change "Renderer" to "Wiki Style Renderer"

### Duplicate post-mortem error

**Symptoms**: Error "Incident already has a Jira post-mortem" but user wants to create it.

**Causes**:
- Post-mortem was created but user didn't see it (network issue)
- Database inconsistency

**Solutions**:
1. Check if post-mortem exists: `python manage.py shell -c "from firefighter.jira_app.models import JiraPostMortem; print(JiraPostMortem.objects.filter(incident_id=123).first())"`
2. If it exists, show user the link
3. If it doesn't exist but error persists, check database constraints

## Testing

### Unit Tests

**File**: `tests/test_jira_app/test_models.py`

```bash
# Run JiraPostMortem model tests
ENABLE_JIRA=true pdm run pytest tests/test_jira_app/test_models.py -v

# Expected: 6 passed
```

**Coverage**: 100% on `JiraPostMortem` model

### Integration Testing

Create a test script to verify end-to-end flow:

```python
# tests/integration/test_jira_postmortem.py
import pytest
from firefighter.incidents.factories import IncidentFactory
from firefighter.confluence.models import PostMortem
from firefighter.jira_app.models import JiraPostMortem

@pytest.mark.django_db
def test_dual_mode_postmortem_creation(settings):
    """Test creating post-mortem in dual mode."""
    settings.ENABLE_CONFLUENCE = True
    settings.ENABLE_JIRA_POSTMORTEM = True

    incident = IncidentFactory()

    # Create post-mortems
    confluence_pm, jira_pm = PostMortem.objects.create_postmortem_for_incident(incident)

    # Verify both created
    assert confluence_pm is not None
    assert jira_pm is not None

    # Verify relationships
    assert incident.postmortem_for == confluence_pm
    assert incident.jira_postmortem_for == jira_pm

    # Verify URLs
    assert "confluence" in confluence_pm.page_url.lower()
    assert "jira" in jira_pm.issue_url.lower()
```

## Best Practices

### 1. Template Customization

If you need to customize templates:

1. Copy templates from `src/firefighter/jira_app/templates/jira/postmortem/`
2. Modify as needed (maintain Wiki Markup format)
3. Place in your custom templates directory
4. Django will use your custom templates (template override)

### 2. Custom Field Management

Keep custom field IDs in environment variables, not hardcoded:

```python
# ✅ Good - configurable
self.field_ids = settings.JIRA_POSTMORTEM_FIELDS

# ❌ Bad - hardcoded
fields = {
    "customfield_12699": incident_summary,
    "customfield_12700": timeline,
}
```

### 3. Error Handling

Always handle Jira API errors gracefully:

```python
try:
    jira_pm = jira_postmortem_service.create_postmortem_for_incident(incident)
except JiraAPIError as e:
    logger.error(f"Failed to create Jira post-mortem: {e}")
    # Fall back to Confluence or show error to user
except ValueError as e:
    # Post-mortem already exists
    logger.warning(f"Post-mortem already exists: {e}")
```

### 4. Migration Strategy

**Recommended approach**:

1. **Week 1**: Deploy with dual mode, monitor for issues
2. **Week 2**: Train team on new Jira post-mortems
3. **Week 3**: Disable Confluence for new post-mortems
4. **Week 4+**: Migrate old Confluence post-mortems to Jira (optional)

## Performance Considerations

### Database Queries

Post-mortem creation involves multiple queries:

1. Check existing post-mortems (2 queries: `hasattr` checks)
2. Fetch incident data (1 query, with prefetch for relations)
3. Fetch commander role (1 query with `filter().first()`)
4. Create Jira issue (1 external API call)
5. Assign to commander (1 external API call)
6. Send Slack notification (1 external API call)
7. Create `JiraPostMortem` record (1 query)

**Optimization**: Consider using `select_related` / `prefetch_related` when fetching incident:

```python
incident = Incident.objects.select_related(
    'priority',
    'incident_category',
    'created_by'
).prefetch_related(
    'roles_set__user__jira_user',
    'roles_set__role_type'
).get(id=incident_id)
```

### Async Considerations

Currently, post-mortem creation is **synchronous** (blocks modal response).

**Future improvement**: Move to Celery task for async processing:

```python
@shared_task
def create_postmortem_async(incident_id: int, created_by_id: int | None = None):
    """Create post-mortem asynchronously."""
    incident = Incident.objects.get(id=incident_id)
    created_by = User.objects.get(id=created_by_id) if created_by_id else None

    PostMortem.objects.create_postmortem_for_incident(incident)
```

## Related Documentation

- [JIRA Integration](jira-integration.md) - General Jira integration overview
- [Test Configuration](test-config.md) - Testing setup for Jira tests
- [Incident Workflow](incident-workflow.md) - Incident workflow and post-mortem requirements

## Changelog

### v0.0.21 (2025-11-06)

- ✅ Initial implementation of Jira post-mortem support
- ✅ Added `JiraPostMortem` model
- ✅ Added 5 Jira Wiki Markup templates
- ✅ Implemented `JiraPostMortemService` with auto-assignment and notifications
- ✅ Extended `JiraClient` with `create_issue()` and `assign_issue()` methods
- ✅ Updated `PostMortemManager` to support dual backends
- ✅ Updated Slack modal to display both Confluence and Jira post-mortems
- ✅ Added configuration via `ENABLE_JIRA_POSTMORTEM` feature flag

## Support

For issues or questions:

1. **GitHub Issues**: https://github.com/ManoManoTech/firefighter-incident/issues
2. **Internal Slack**: #firefighter-support
3. **Documentation**: https://docs.firefighter.example.com

---

*Last updated: 2025-11-06*
*Version: 0.0.21*
