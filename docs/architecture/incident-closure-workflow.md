# Incident Closure Workflow

This document describes the complete incident closure workflow in FireFighter, including the different paths and requirements for closing incidents based on priority and status.

## Overview

FireFighter supports multiple ways to close incidents, with different requirements based on the incident's priority level and current status. The workflow ensures that critical incidents (P1/P2) follow proper post-mortem procedures, while allowing more streamlined closure for lower priority incidents.

## Workflow Diagram

```mermaid
graph TD
    A[Incident Created] --> B[Opened]
    B --> C[Investigating]
    C --> D[Mitigating]
    D --> E[Mitigated]

    %% P1/P2 PRD Path (Post-mortem Required)
    E --> F{P1/P2 in PRD?}
    F -->|Yes| G[Post-mortem]
    G --> H[Closed]

    %% P3+ Path (No Post-mortem Required)
    F -->|No| H

    %% Closure with Reason (Any Priority)
    B -->|Reason Required| I[Closure Reason Form]
    C -->|Reason Required| I
    I --> H

    %% Normal Workflow Closure
    E -->|Normal Close| H
    G -->|Normal Close| H

    %% Status Labels
    B[Opened<br/>⚠️ Reason required for closure]
    C[Investigating<br/>⚠️ Reason required for closure]
    D[Mitigating]
    E[Mitigated]
    G[Post-mortem<br/>✅ Can close normally]
    H[Closed<br/>📁 Channel archived]
    I[Closure Reason<br/>🗃️ Mandatory form]
```

## Closure Methods

### 1. Normal Workflow Closure

**Path**: `Mitigated` → `Closed` (or `Post-mortem` → `Closed` for P1/P2)

- **When**: Incident has been properly resolved through the normal workflow
- **Requirements**:
  - Status must be `Mitigated` or higher
  - For P1/P2 in PRD: Must complete post-mortem first
- **Triggered via**:
  - `/incident close` command
  - Update status to "Closed" (when allowed)

### 2. Closure with Reason

**Path**: `Opened/Investigating` → `Closure Reason Form` → `Closed`

- **When**: Incident needs to be closed without following the complete workflow
- **Use cases**:
  - Duplicate incidents
  - False alarms
  - No actual anomaly
  - User error
- **Requirements**:
  - Mandatory closure reason selection
  - Optional reference to related incident/link
  - Closure message explaining the decision
- **Triggered via**:
  - `/incident close` command (shows reason form automatically)
  - Update status to "Closed" from early statuses (shows reason form automatically)

## Priority-Based Rules

### P1/P2 Incidents in PRD Environment

- **Post-mortem Required**: Must complete post-mortem before normal closure
- **Workflow**: `Mitigated` → `Post-mortem` → `Closed`
- **Direct Closure**: Still available from `Opened/Investigating` with reason

### P3/P4/P5 Incidents

- **Post-mortem Optional**: Can close directly from `Mitigated` status
- **Workflow**: `Mitigated` → `Closed`
- **Direct Closure**: Available from `Opened/Investigating` with reason

## Status Restrictions

### From "Opened" or "Investigating"

- ❌ **Cannot close normally** without reason
- ✅ **Can close with reason** (mandatory closure reason form)
- **All priorities** follow the same rule

### From "Mitigating" or "Mitigated"

- ✅ **Can close normally** (P3+ incidents)
- ❌ **Cannot close normally** (P1/P2 in PRD - must go through post-mortem)

### From "Post-mortem"

- ✅ **Can close normally** (all priorities)

## Closure Reason Types

When closing with a reason, the following options are available:

- **DUPLICATE**: Duplicate of another incident
- **FALSE_POSITIVE**: False alarm - no actual issue
- **SUPERSEDED**: Superseded by another incident
- **EXTERNAL**: External dependency/known issue
- **CANCELLED**: Cancelled - no longer relevant

*Note: "RESOLVED" is excluded from early closure reasons as it's reserved for normal workflow closure only.*

## Technical Implementation

### Key Components

1. **UpdateStatusForm.requires_closure_reason()**: Determines when closure reason is needed
   - Location: `src/firefighter/incidents/forms/update_status.py`

2. **IncidentClosureReasonForm**: Handles closure reason input
   - Location: `src/firefighter/incidents/forms/closure_reason.py`

3. **ClosureReason Enum**: Defines available closure reasons
   - Location: `src/firefighter/incidents/enums.py`

4. **Modal Utils**: Circular import resolution and modal routing
   - Location: `src/firefighter/slack/views/modals/utils.py`

5. **Slack Integration**: Modal handlers for closure reason collection
   - Close Modal: Redirects to reason form when needed
   - Update Status Modal: Shows reason form for early closure attempts

### Closure Reason Detection Logic

The system determines if a closure reason is required based on the incident's current status:

```python
@staticmethod
def requires_closure_reason(incident: Incident, target_status: IncidentStatus) -> bool:
    """Check if closing this incident to the target status requires a closure reason."""
    if target_status != IncidentStatus.CLOSED:
        return False

    current_status = incident.status

    # Require reason if closing from Opened or Investigating (for any priority)
    return current_status.value in [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]
```

### Database Fields

Closure reason information is stored in the incident model:

- `closure_reason`: Selected reason code (ClosureReason enum)
- `closure_reference`: Optional reference to related incident or external link

## User Experience

### Slack Commands

- **`/incident close`**:
  - Shows normal close form if status allows
  - Shows closure reason form if closing from early status
  - Shows error message if prerequisites not met

- **`/incident update`**:
  - Shows normal update form
  - Intercepts "Closed" selection from early statuses
  - Automatically pushes closure reason form when needed

### Modal Flow

1. User attempts to close incident
2. System checks current status and requirements
3. Routes to appropriate modal:
   - Normal close form (if status allows)
   - Closure reason form (if early status)
   - Error message (if prerequisites not met)

## Benefits

- **Streamlined Process**: Single workflow for all closure scenarios
- **Proper Documentation**: Reasons captured for audit and analysis
- **Flexibility**: Supports both rigorous and quick closure paths
- **Consistency**: Same logic applies across all interfaces
- **User-Friendly**: Automatic detection and routing to correct form
