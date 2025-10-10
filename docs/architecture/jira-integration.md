# JIRA Integration Architecture

## Overview

The RAID module provides comprehensive bidirectional synchronization between Impact incidents and JIRA tickets, ensuring data consistency across both platforms.

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

## Bidirectional Sync Flows

### Impact → JIRA Sync

**Trigger**: Incident field updates in Impact
**Handler**: `sync_incident_changes_to_jira()`

**Syncable Fields**:
- `title` → `summary`
- `description` → `description`
- `priority` → `priority` (with value mapping)
- `status` → `status` (with transitions)
- `commander` → `assignee`

**Process**:
1. Check if RAID is enabled
2. Validate update_fields parameter
3. Filter for syncable fields only
4. Apply loop prevention cache
5. Call `sync_incident_to_jira()`

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
    "Open": IncidentStatus.INVESTIGATING,
    "To Do": IncidentStatus.INVESTIGATING,
    "In Progress": IncidentStatus.MITIGATING,
    "In Review": IncidentStatus.MITIGATING,
    "Resolved": IncidentStatus.MITIGATED,
    "Done": IncidentStatus.MITIGATED,
    "Closed": IncidentStatus.POST_MORTEM,
    "Reopened": IncidentStatus.INVESTIGATING,
    "Blocked": IncidentStatus.MITIGATING,
    "Waiting": IncidentStatus.MITIGATING,
}
```

**Impact → JIRA**:
```python
IMPACT_TO_JIRA_STATUS_MAP = {
    IncidentStatus.OPEN: "Open",
    IncidentStatus.INVESTIGATING: "In Progress",
    IncidentStatus.MITIGATING: "In Progress",
    IncidentStatus.MITIGATED: "Resolved",
    IncidentStatus.POST_MORTEM: "Closed",
    IncidentStatus.CLOSED: "Closed",
}
```

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

## Loop Prevention

### Cache-Based Mechanism

**Function**: `should_skip_sync()`
**Cache Key Format**: `sync:{entity_type}:{entity_id}:{direction}`
**Timeout**: 30 seconds

**Process**:
1. Check if sync recently performed
2. Set cache flag during sync
3. Automatic expiration prevents permanent blocks

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
