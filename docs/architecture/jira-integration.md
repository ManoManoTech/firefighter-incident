# JIRA Integration Architecture

## Overview

The RAID module provides comprehensive bidirectional synchronization between Impact incidents and JIRA tickets, ensuring data consistency across both platforms.

✅ **Applies to all P1-P5**:
- All priorities create both `Incident` objects AND JIRA tickets
- The JIRA integration works identically for all priorities

✅ **Double sync (both directions)**:

- Impact → Jira: on incident updates (status, priority, title, description, commander) via `incident_updated` signals; admin saves fall back to post_save handlers for status/priority
- Jira → Impact: on Jira webhooks (status, priority, mapped fields) via webhook handlers
- Loop-prevention cache ensures a change coming from one side is not re-sent back immediately

See [incident-workflow.md](incident-workflow.md) for architecture overview.

## Synchronization Architecture

### Core Components

1. **Sync Engine** (`src/firefighter/raid/sync.py`)
   - Central synchronization logic
   - Loop prevention mechanism
   - Field mapping and validation

2. **Signal Handlers** (`src/firefighter/raid/signals/`)
   - `incident_updated_sync.py` - Handles Impact → JIRA sync
   - `incident_created.py` - Handles incident creation events

3. **JIRA Client** (`src/firefighter/raid/client.py`)
   - Extended JIRA client with RAID-specific methods
   - Issue creation, updates, and transitions
   - Attachment handling

## JIRA Ticket Creation

### Initial Ticket Creation

**Function**: `prepare_jira_fields()` in `src/firefighter/raid/forms.py`

Centralizes all JIRA field preparation for both P1-P3 and P4-P5 workflows.

**P1-P3 (Critical)**:
- Trigger: `incident_channel_done` signal
- Handler: `src/firefighter/raid/signals/incident_created.py`
- Flow: Create Incident → Create Slack channel → Signal triggers JIRA ticket

**P4-P5 (Normal)**:
- Trigger: Form submission
- Handler: `UnifiedIncidentForm._trigger_normal_incident_workflow()`
- Flow: Direct call to `jira_client.create_issue()`

### Custom Fields Mapping

**Always Passed**:
- `customfield_11049` (environments): List of env values (PRD, STG, INT)
  - P1-P3: First environment only
  - P4-P5: All selected environments
- `customfield_10201` (platform): Platform value (platform-FR, platform-All, etc.)
- `customfield_10936` (business_impact): Computed from impacts_data

**Impact-Specific**:
- Customer: `zendesk_ticket_id`
- Seller: `seller_contract_id`, `zoho_desk_ticket_id`, `is_key_account`, `is_seller_in_golden_list`
- P4-P5: `suggested_team_routing`

**Bug Fix GT-1334 (October 2025)**: P4-P5 incidents were not passing custom fields. Fixed by creating `prepare_jira_fields()` to centralize field preparation for both workflows.

## Bidirectional Sync Flows

### Impact → JIRA Sync

**Trigger**: Incident field updates in Impact (via `incident_updated` with `updated_fields`), plus admin saves via post_save fallbacks for status/priority.
**Handlers**: `incident_updated_close_ticket_when_mitigated_or_postmortem` (status), `incident_updated_sync_priority_to_jira` (priority), post_save fallbacks for both.

**Syncable Fields**:
- `title` → `summary`
- `description` → `description`
- `priority` → Jira `customfield_11064` (numeric 1–5, or mapped option)
- `status` → Jira status (transitions via workflow)
- `commander` → `assignee`

**Process**:
1. Check if RAID is enabled
2. Validate/update_fields
3. Apply loop prevention
4. Push status (Impact→Jira map)
5. Push priority to Jira `customfield_11064`

### JIRA → Impact Sync

**Trigger**: JIRA webhook updates
**Handler**: `handle_jira_webhook_update()`

**Process**:
1. Parse webhook changelog data
2. Identify changed fields
3. Apply appropriate sync functions:
   - `sync_jira_status_to_incident()`
   - `sync_jira_priority_to_incident()`
   - `sync_jira_fields_to_incident()`

## Field Mapping

### Status Mapping

**JIRA → Impact**:
```python
JIRA_TO_IMPACT_STATUS_MAP = {
    "Incoming": IncidentStatus.OPEN,
    "Pending resolution": IncidentStatus.OPEN,
    "in progress": IncidentStatus.MITIGATING,  # change to INVESTIGATING if desired
    "Reporter validation": IncidentStatus.MITIGATED,
    "Closed": IncidentStatus.CLOSED,
}
```

**Impact → JIRA**:
```python
IMPACT_TO_JIRA_STATUS_MAP = {
    IncidentStatus.OPEN: "Incoming",
    IncidentStatus.INVESTIGATING: "in progress",
    IncidentStatus.MITIGATING: "in progress",
    IncidentStatus.MITIGATED: "Reporter validation",
    IncidentStatus.POST_MORTEM: "Reporter validation",
    IncidentStatus.CLOSED: "Closed",
}
```

**Status override note**: If Jira “In Progress” should map to Impact INVESTIGATING (instead of MITIGATING), update the `JIRA_TO_IMPACT_STATUS_MAP` accordingly.

### Priority Mapping

**JIRA → Impact**:
```python
JIRA_TO_IMPACT_PRIORITY_MAP = {
    "Highest": 1,  # P1 - Critical
    "High": 2,     # P2 - High
    "Medium": 3,   # P3 - Medium
    "Low": 4,      # P4 - Low
    "Lowest": 5,   # P5 - Lowest
}
```

**Impact → JIRA**:
Uses the numeric Impact priority (1–5) and writes to Jira `customfield_11064` (custom priority field). Admin saves and UI edits both sync via signals/post_save fallback.

## Loop Prevention

### Cache-Based Mechanism

**Function**: `should_skip_sync()`
**Cache Key Format**: `sync:{entity_type}:{entity_id}:{direction}`
**Timeout**: 30 seconds

**Process**:
1. Check if sync recently performed
2. Set cache flag during sync
3. Automatic expiration prevents permanent blocks

**Webhook bounce guard**: Impact→Jira writes a short-lived cache key per change (`sync:impact_to_jira:{incident_id}:{field}:{value}`). Jira webhook processing checks and clears that key to skip the mirrored change, preventing loops for status and priority (including `customfield_11064`).

### Sync Directions

```python
class SyncDirection(Enum):
    IMPACT_TO_JIRA = "impact_to_jira"
    JIRA_TO_IMPACT = "jira_to_impact"
    IMPACT_TO_SLACK = "impact_to_slack"
    SLACK_TO_IMPACT = "slack_to_impact"
```

## Error Handling

### Transaction Management

- All sync operations wrapped in `transaction.atomic()`
- Rollback on any failure
- Detailed error logging with context

### Graceful Degradation

- Missing JIRA tickets: Log warning, continue
- Field validation errors: Skip invalid fields
- Network failures: Retry mechanism via Celery

## IncidentUpdate Integration

### Dual Sync Paths

1. **Direct Incident Updates**
   - Uses `update_fields` parameter
   - More efficient for bulk operations

2. **IncidentUpdate Records**
   - Tracks individual field changes
   - Preserves change history
   - Anti-loop detection for JIRA-originated updates

### Loop Detection for IncidentUpdates

**Pattern**: Updates created by sync have:
- `created_by = None` (system update)
- `message` contains "from Jira"

```python
if instance.created_by is None and "from Jira" in (instance.message or ""):
    logger.debug("Skipping sync - appears to be from Jira sync")
    return
```

## Configuration

### Required Settings

- `ENABLE_RAID = True` - Enable RAID module
- `RAID_JIRA_PROJECT_KEY` - Default JIRA project
- `RAID_JIRA_INCIDENT_CATEGORY_FIELD` - Custom field mapping
- `RAID_TOOLBOX_URL` - Integration URL

### Environment Variables

- Database: `POSTGRES_DB`, `POSTGRES_SCHEMA`
- Feature flags: `ENABLE_JIRA`, `ENABLE_RAID`
- Slack: `FF_SLACK_SKIP_CHECKS` (for testing)

## Testing Sync Functionality

### Key Test Files

- `tests/test_raid/test_sync.py` - Core sync logic
- `tests/test_raid/test_sync_signals.py` - Signal handlers
- `tests/test_raid/test_webhook_serializers.py` - Webhook processing

### Test Patterns

```python
@patch("firefighter.raid.sync.sync_incident_to_jira")
@override_settings(ENABLE_RAID=True)
def test_sync_incident_changes(self, mock_sync):
    mock_sync.return_value = True
    # Test sync triggering and field filtering
```

## Performance Considerations

### Optimization Strategies

1. **Field Filtering**: Only sync changed fields
2. **Batch Operations**: Group related updates
3. **Async Processing**: Use Celery for heavy operations
4. **Cache Warming**: Pre-load frequently accessed data

### Monitoring

- Sync success/failure rates
- Performance metrics per sync type
- Error categorization and alerting

## Jira Post-Mortem Integration

### Overview

The Jira post-mortem feature creates dedicated post-mortem issues in Jira when an incident moves to the POST_MORTEM status. This provides a structured place to document root causes, impacts, and mitigation actions.

### Architecture

**Service Layer**: `src/firefighter/jira_app/service_postmortem.py`
- `JiraPostMortemService` - Main service for creating post-mortems
- `create_postmortem_for_incident()` - Creates Jira post-mortem issue
- `_generate_issue_fields()` - Generates content from templates

**Jira Client**: `src/firefighter/jira_app/client.py`
- `create_postmortem_issue()` - Creates the Jira issue
- `_create_issue_link_safe()` - Links post-mortem to incident ticket (robust with fallbacks)
- `assign_issue()` - Assigns to incident commander (graceful failure)

**Signal Handlers**: `src/firefighter/jira_app/signals/`
- `postmortem_created.py` - Triggers post-mortem creation on incident status change
- `incident_key_events_updated.py` - Syncs key events from Slack to Jira timeline

### Post-Mortem Creation Flow

1. **Trigger**: Incident status changes to `POST_MORTEM` (via Slack modal or direct status update)
2. **Signal**: `postmortem_created` signal sent with incident data
3. **Content Generation**: Templates rendered with incident data:
   - `incident_summary.txt` - Priority, category, created_at (excludes Status/Created)
   - `timeline.txt` - Chronological list of status changes and key events
   - `impact.txt` - Business impact description
   - `mitigation_actions.txt` - Actions taken during incident
   - `root_causes.txt` - Placeholder for manual completion
4. **Issue Creation**: Jira post-mortem issue created with generated content
5. **Issue Linking**: Links post-mortem to incident ticket using issue links (not parent-child)
6. **Assignment**: Attempts to assign to incident commander (optional, fails gracefully)
7. **Slack Updates**:
   - Posts notification message in incident channel (pinned)
   - Updates initial incident message with post-mortem link
   - Adds bookmark to channel with post-mortem link

### Issue Linking Strategy

**Problem**: Jira parent-child relationships have strict hierarchy rules. Setting a parent field can fail with:
```
{"errors":{"parentId":"Given parent work item does not belong to appropriate hierarchy."}}
```

**Solution**: Use flexible issue links instead of parent-child relationships.

**Implementation** (`_create_issue_link_safe()`):
1. Validate both issues exist
2. Try multiple link types in order of preference:
   - "Relates" (standard bidirectional link)
   - "Blocks" (alternative link type)
   - "Relates to" (another common variant)
3. Log warnings but don't fail if linking unsuccessful
4. Post-mortem creation always succeeds even if linking fails

**Benefits**:
- Works across any issue types regardless of hierarchy
- Graceful degradation if link types unavailable
- Main workflow never blocked by linking failures

### Timeline Generation

**Template**: `src/firefighter/jira_app/templates/jira/postmortem/timeline.txt`

**Content**:
- Incident creation event
- All status changes with timestamps
- All key events (detected, started, recovered, etc.) with optional messages
- Sorted chronologically ascending by `event_ts`

**Format** (Jira Wiki Markup):
```
h2. Timeline

|| Time || Event ||
| 2025-11-19 10:00 UTC | Incident created (P1) |
| 2025-11-19 10:05 UTC | Status changed to: Investigating |
| 2025-11-19 10:10 UTC | Key event: Detected - Issue first detected |
| 2025-11-19 10:15 UTC | Status changed to: Mitigating |
| 2025-11-19 10:30 UTC | Key event: Recovered - System back to normal |
| 2025-11-19 10:35 UTC | Status changed to: Mitigated |
```

**Key Events Sync**:
- Key events entered in Slack are synced to Jira timeline via `incident_key_events_updated` signal
- Ensures timeline is always up-to-date with the latest incident events

### Graceful Error Handling

**Assignment Failures**:
- `assign_issue()` returns boolean instead of raising exceptions
- Logs WARNING instead of ERROR
- Post-mortem creation succeeds even if commander assignment fails

**Invalid Emojis** (Test Environments):
- Bookmark creation wrapped in try/except `SlackApiError`
- Custom emojis (`:jira_new:`, `:confluence:`) may not exist in test workspaces
- Logs warnings but doesn't fail post-mortem workflow

**Issue Link Failures**:
- Multiple link type fallbacks
- Validates issues before linking
- Post-mortem always created even if linking fails

### Slack Integration

**Notification Message** (`SlackMessageIncidentPostMortemCreated`):
- Posted to incident channel and pinned
- Contains links to all available post-mortems (Confluence + Jira)
- Sent by `postmortem_created_send()` signal handler

**Initial Message Update** (`SlackMessageIncidentDeclaredAnnouncement`):
- The pinned initial incident announcement message is automatically updated
- Shows all post-mortem links alongside incident ticket link
- Uses `SlackMessageStrategy.UPDATE` to update existing message
- Format:
  ```
  :jira_new: <link|Jira ticket>
  :confluence: <link|Confluence Post-mortem>
  :jira_new: <link|Jira Post-mortem (PM-123)>
  ```

**Channel Bookmarks**:
- Bookmarks added for quick access to post-mortems
- Confluence: `:confluence:` emoji
- Jira: `:jira_new:` emoji with issue key
- Gracefully handles missing custom emojis in test environments

### Configuration

**Settings** (`settings.py`):
```python
# Post-mortem project and issue type
JIRA_POSTMORTEM_PROJECT_KEY = "POSTMORTEM"  # or same as incident project
JIRA_POSTMORTEM_ISSUE_TYPE = "Post-mortem"

# Custom field IDs for post-mortem content
JIRA_POSTMORTEM_FIELDS = {
    "incident_summary": "customfield_12699",
    "timeline": "customfield_12700",
    "root_causes": "customfield_12701",
    "impact": "customfield_12702",
    "mitigation_actions": "customfield_12703",
    "incident_category": "customfield_12369",
}
```

**Environment Variables**:
```bash
ENABLE_JIRA_POSTMORTEM=true  # Enable Jira post-mortem feature
```

### Testing

**Test Files**:
- `tests/test_jira_app/test_postmortem_service.py` - Service layer tests (4 tests)
  - Incident summary excludes Status and Created fields
  - Timeline includes status changes
  - Prefetches incident updates
  - Handles assignment failure gracefully
- `tests/test_jira_app/test_postmortem_issue_link.py` - Issue linking tests (6 tests)
  - Link creation success on first try
  - Fallback to alternative link types
  - Graceful failure scenarios
  - Post-mortem creation succeeds even if link fails
- `tests/test_jira_app/test_timeline_template.py` - Timeline generation tests (2 tests)
  - Chronological ordering of events
  - Handling key events with/without messages

**Test Patterns**:
```python
@pytest.mark.django_db
@patch("firefighter.jira_app.service_postmortem.JiraClient")
def test_create_postmortem(mock_jira_client):
    # Mock Jira client responses
    mock_client_instance = MagicMock()
    mock_client_instance.create_postmortem_issue.return_value = {
        "id": "12345",
        "key": "TEST-123",
    }
    mock_jira_client.return_value = mock_client_instance

    # Create post-mortem
    service = JiraPostMortemService()
    jira_pm = service.create_postmortem_for_incident(incident, created_by=user)

    # Verify
    assert jira_pm.jira_issue_key == "TEST-123"
```

### Database Models

**JiraPostMortem** (`src/firefighter/jira_app/models.py`):
- `incident` - OneToOne to Incident (related_name: `jira_postmortem_for`)
- `jira_issue_key` - Jira issue key (e.g., "PM-123")
- `jira_issue_id` - Jira internal ID
- `created_by` - User who created the post-mortem
- `issue_url` - Property that generates full Jira URL

### Key Features

1. **Automatic Content Generation**: Post-mortem content generated from incident data using Django templates
2. **Robust Issue Linking**: Multiple fallback strategies for linking to incident tickets
3. **Graceful Degradation**: All optional operations (linking, bookmarks, assignments) fail gracefully
4. **Real-time Slack Updates**: Initial message updated automatically when post-mortem created
5. **Chronological Timeline**: Complete incident timeline with status changes and key events
6. **Commander Assignment**: Automatically assigns post-mortem to incident commander if available

### Best Practices

1. **Field Mapping**: Keep custom field IDs in settings, not hardcoded
2. **Error Handling**: Optional operations should never block the main workflow
3. **ORM Caching**: Always `refresh_from_db()` in signals when checking for newly created relationships
4. **Template Rendering**: Use Django templates for Jira Wiki Markup content generation
5. **Test Coverage**: Test all failure scenarios, not just happy paths
