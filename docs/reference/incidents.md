
# Incidents

The incidents module is the core of FireFighter, managing incident lifecycle, priorities, and integrations.

## Priority System

FireFighter uses a 5-level priority system (P1-P5) to categorize incident severity:

### Priority Levels

| Priority | Emoji | Level | Description | Example |
|----------|-------|-------|-------------|---------|
| P1 | 🔥 | Critical | Complete service outage, system-wide failure | Payment system down, entire website offline |
| P2 | 🚨 | High | Major functionality impaired, significant user impact | Core feature broken, major performance degradation |
| P3 | ⚠️ | Medium | Minor functionality affected, moderate impact | Non-critical feature issue, isolated component problem |
| P4 | 📢 | Low | Small issues, minimal impact | UI glitches, minor bugs in secondary features |
| P5 | 💡 | Lowest | Cosmetic issues, enhancement requests | Typos, improvement suggestions, non-urgent requests |

### Priority Usage

**Incident Creation**: When creating an incident, the priority determines:
- Notification urgency and channels
- Automatic escalations (PagerDuty for P1/P2)
- Jira ticket priority mapping
- SLA expectations

**Integration Mapping**:
- **Jira**: P1-P5 maps directly to Jira priorities 1-5
- **PagerDuty**: P1-P2 typically trigger immediate escalation
- **Slack**: Higher priorities get broader notification reach

### Priority Assignment Guidelines

**P1 (Critical)** - Use when:
- Complete service unavailability
- Data loss or corruption
- Security breaches
- Payment processing failures

**P2 (High)** - Use when:
- Major feature completely broken
- Significant performance degradation
- Multiple users affected by the same issue

**P3 (Medium)** - Use when:
- Single feature partially broken
- Workaround exists
- Limited user impact

**P4 (Low)** - Use when:
- Minor UI issues
- Edge case bugs
- Enhancement requests with business value

**P5 (Lowest)** - Use when:
- Cosmetic improvements
- Documentation updates
- Nice-to-have features

!!! note "Priority Validation"
    Invalid priority values automatically fallback to P1 to ensure critical handling.

## API Reference

::: firefighter.incidents
