# JIRA Post-mortem Integration

> **Status**: ✅ Implemented (v0.0.21+)
> **Purpose**: Create post-mortems in JIRA instead of (or alongside) Confluence

---

## Overview

FireFighter supports creating post-mortems in JIRA as an alternative to Confluence.

**What happens**:
1. User clicks "Create post-mortem" in Slack
2. JIRA issue created with pre-populated fields
3. Auto-assigned to incident commander (if they have JIRA account)
4. Slack notification sent with link

---

## Architecture

```
Slack Modal
    ↓
PostMortemManager
    ├─ Confluence Service (existing)
    └─ JiraPostMortemService (new)
        ├─ Create JIRA Issue
        ├─ Assign to Commander
        └─ Notify Slack Channel
```

---

## Configuration

### Required (if enabling JIRA post-mortems)

```bash
ENABLE_JIRA_POSTMORTEM=true
JIRA_POSTMORTEM_PROJECT_KEY=INCIDENT
JIRA_POSTMORTEM_ISSUE_TYPE="Post-mortem"
```

### Custom Field IDs (optional)

```bash
JIRA_FIELD_INCIDENT_SUMMARY=customfield_12699
JIRA_FIELD_TIMELINE=customfield_12700
JIRA_FIELD_ROOT_CAUSES=customfield_12701
JIRA_FIELD_IMPACT=customfield_12702
JIRA_FIELD_MITIGATION_ACTIONS=customfield_12703
JIRA_FIELD_INCIDENT_CATEGORY=customfield_12369
```

---

## Deployment Modes

| Mode | Config | Behavior |
|------|--------|----------|
| **Confluence only** | `ENABLE_CONFLUENCE=true`, `ENABLE_JIRA_POSTMORTEM=false` | Legacy (Confluence only) |
| **JIRA only** | `ENABLE_CONFLUENCE=false`, `ENABLE_JIRA_POSTMORTEM=true` | Target (JIRA only) |
| **Dual mode** | Both enabled | Migration (both backends) |

---

## Pre-populated Fields

| Field | Content |
|-------|---------|
| **Incident Summary** | Channel link, priority, status, date, description |
| **Timeline** | Created time + key events (TODO markers for users) |
| **Impact** | Affected systems, duration (TODO markers) |
| **Mitigation Actions** | Related JIRA follow-up links (TODO markers) |
| **Root Causes** | Empty (TODO - users complete) |

---

## Features

### Automatic Creation

```
User submits → Validate → Create issue → Assign → Notify → Save DB
```

**Error handling**:
- Assignment fails? → Log warning, continue
- Notification fails? → Log error, continue
- JIRA API fails? → Raise exception, rollback

### Commander Assignment

If commander has linked JIRA account → Auto-assign to them.
If not → Continue (logged as warning).

### Slack Notifications

Modal shows links to existing post-mortems (Confluence and/or JIRA).

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Silent creation failure | Both backends disabled or credentials wrong | Check env vars, check logs |
| Commander not assigned | No JIRA account linked to user | User needs JIRA account |
| Slack notification missing | No incident conversation or bot not in channel | Verify bot is in incident channel |
| Wiki markup not rendering | Custom field type wrong in JIRA | Set renderer to "Wiki Style Renderer" |

---

## Implementation

**Core files**:
- `src/firefighter/jira_app/models.py` - `JiraPostMortem` model
- `src/firefighter/jira_app/service_postmortem.py` - `JiraPostMortemService`
- `src/firefighter/jira_app/templates/jira/postmortem/` - Templates (Wiki Markup)
- `src/firefighter/confluence/models.py` - `PostMortemManager`

**Methods**:
- `jira_postmortem_service.create_postmortem_for_incident(incident, created_by)` - Create post-mortem
- `PostMortem.objects.create_postmortem_for_incident(incident)` - Manager (handles both backends)

See source code for implementation details.

---

## Related

- [JIRA Integration](jira-integration.md) - General JIRA sync
- [Incident Workflow](incident-workflow.md) - Post-mortem requirements
- [Architecture Overview](overview.md) - Project structure

