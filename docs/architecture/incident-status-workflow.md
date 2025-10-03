# Incident Status Workflow

This document describes the exact incident status workflow implemented in FireFighter.

## Overview

The incident status workflow differs based on the incident priority:

- **P1/P2 incidents**: Require post-mortem completion in PRD environment
- **P3/P4/P5 incidents**: Do not require post-mortem

## Workflow Transitions

### P1/P2 Incidents (Priority 1-2 in PRD Environment)

```
OPEN → [INVESTIGATING, CLOSED (with reason)]
INVESTIGATING → [FIXING, CLOSED (with reason)]
FIXING → [FIXED]
FIXED → [POST_MORTEM]
POST_MORTEM → [CLOSED]
```

**Key Rules for P1/P2:**
- **Post-mortem is mandatory** for P1/P2 incidents in PRD environment
- **Cannot skip POST_MORTEM status** - must go through it before closing
- **From FIXING**: Can only go to FIXED, not to POST_MORTEM or CLOSED
- **From FIXED**: Can only go to POST_MORTEM, not directly to CLOSED
- **Closure with reason**: Only allowed from OPEN and INVESTIGATING statuses

### P3/P4/P5 Incidents (Priority 3+ or Non-PRD)

```
OPEN → [INVESTIGATING, CLOSED (with reason)]
INVESTIGATING → [FIXING, CLOSED (with reason)]
FIXING → [FIXED]
FIXED → [CLOSED]
```

**Key Rules for P3+:**
- **No post-mortem required** - POST_MORTEM status is not available
- **Direct closure**: Can close directly from FIXED without intermediate steps
- **Closure with reason**: Only allowed from OPEN and INVESTIGATING statuses

## Closure Reason Requirements

A closure reason form is **required** when closing an incident directly from:
- **OPEN** status
- **INVESTIGATING** status

This applies to **all priority levels** (P1-P5).

## Implementation Details

### Status Values
- `OPEN = 10`
- `INVESTIGATING = 20`
- `FIXING = 30` (labeled as "Mitigating")
- `FIXED = 40` (labeled as "Mitigated")
- `POST_MORTEM = 50`
- `CLOSED = 60`

### Form Logic Location
The workflow logic is implemented in:
- **Form**: `src/firefighter/incidents/forms/update_status.py`
- **Enum**: `src/firefighter/incidents/enums.py`
- **Tests**: `tests/test_incidents/test_forms/test_workflow_transitions.py`

### Priority Detection
P1/P2 incidents requiring post-mortem are detected by:
```python
requires_postmortem = (
    incident.priority
    and incident.environment
    and incident.priority.needs_postmortem
    and incident.environment.value == "PRD"
)
```

## Testing

Comprehensive workflow tests are located in:
- `tests/test_incidents/test_forms/test_workflow_transitions.py` - Complete workflow validation
- `tests/test_incidents/test_forms/test_update_status_workflow.py` - Legacy tests (some skipped)
- `tests/test_slack/views/modals/test_update_status.py` - Slack integration tests

## Migration Notes

This workflow was implemented to replace a previous more permissive workflow that allowed invalid transitions. The new implementation:

1. **Restricts transitions** to exactly match the business workflow requirements
2. **Enforces post-mortem** completion for P1/P2 incidents in PRD
3. **Simplifies P3+ workflow** by removing unnecessary post-mortem steps
4. **Validates closure reasons** for early-stage closures

## Related Files

- **Forms**: `src/firefighter/incidents/forms/update_status.py`
- **Enums**: `src/firefighter/incidents/enums.py`
- **Slack Integration**: `src/firefighter/slack/views/modals/update_status.py`
- **Utilities**: `src/firefighter/slack/views/modals/utils.py`
- **Tests**: `tests/test_incidents/test_forms/test_workflow_transitions.py`