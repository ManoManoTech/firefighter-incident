
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

## Authentication

The external ticket creation endpoint (`POST /api/v2/firefighter/raid/jira_bot`) requires Bearer token authentication.

Each caller must use a dedicated `APIToken`, generated from the Django back-office at `/admin/api/apitokenproxy/`. Requests must include the header:

```
Authorization: Bearer <token>
```

### Common pitfall: HTML formatting in copy-pasted tokens

The Django admin renders the token with text styling inherited from `rest_framework.authtoken`. A regular copy-paste from the admin into a tool that accepts rich-text input (Landbot Webhook header values, some no-code platforms, Notion, etc.) silently carries the styling as inline HTML. The receiving tool displays the value as plain text, but the actual outgoing header looks like:

```
Authorization: <h2>Bearer <token></h2>
```

The endpoint then returns `401 not_authenticated` because DRF cannot parse the keyword.

**Workaround:** when copying a token from the admin, paste with `Cmd+Shift+V` (paste without formatting) or type the token by hand.

**Debug tip:** if a third-party integration fails with `not_authenticated` while `curl` with the same token succeeds, route the integration's webhook to [webhook.site](https://webhook.site) to inspect the actual `Authorization` header it emits.

## API Reference

::: firefighter.raid
