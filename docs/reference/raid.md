
# RAID Module

The RAID module provides enhanced Jira integration for incident management and external ticket creation.

## Overview

RAID (Request And Issue Database) extends FireFighter's capabilities with:

- **Automatic Jira ticket creation** for incidents
- **External API for ticket creation** (Landbot integration)
- **Smart user resolution** based on email domains
- **Priority mapping** from P1-P5 to Jira priorities
- **Attachment handling** for external submissions
- **Slack notifications** for ticket updates

## Priority Mapping

The RAID module supports full P1-P5 priority mapping:

| Priority | Level | Jira Priority | Use Case |
|----------|-------|---------------|----------|
| P1 | Critical | 1 | System outages, complete service failures |
| P2 | High | 2 | Major functionality impaired, significant impact |
| P3 | Medium | 3 | Minor functionality affected, moderate impact |
| P4 | Low | 4 | Small issues, minimal impact |
| P5 | Lowest | 5 | Cosmetic issues, enhancement requests |

## User Resolution

The module handles user resolution for external ticket creation:

1. **Internal users**: Direct mapping from email to existing users
2. **External users**: Email domain-based routing to default Jira users
3. **Slack fallback**: Attempts to find users via Slack integration
4. **Default assignment**: Falls back to configured default Jira user

## API Reference

::: firefighter.raid
