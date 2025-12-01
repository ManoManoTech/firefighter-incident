# Incident Workflow

> All priorities (P1-P5) follow the same workflow. Differences are in Slack channels and post-mortem requirements.

---

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CREATION (All P1-P5 identical)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ 1. User opens incident form → Selects impacts → Priority auto-determined   │
│ 2. UnifiedIncidentForm (same for all priorities)                           │
│ 3. Creates:                                                                │
│    ✅ Incident object (all P1-P5)                                          │
│    ✅ Jira ticket (all P1-P5)                                              │
│    ✅ Slack channel (P1-P3 only)  ← Only difference in creation            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
        ┌───────────────────────────┴───────────────────────────┐
        ↓                                                       ↓
┌────────────────────────────┐                     ┌────────────────────────────┐
│ P1/P2 (with Post-Mortem)   │                     │ P3-P5 (no Post-Mortem)     │
├────────────────────────────┤                     ├────────────────────────────┤
│ OPEN                       │                     │ OPEN                       │
│   ↓                        │                     │   ↓                        │
│ INVESTIGATING              │                     │ INVESTIGATING              │
│   ↓                        │                     │   ↓                        │
│ MITIGATING                 │                     │ MITIGATING                 │
│   ↓                        │                     │   ↓                        │
│ MITIGATED                  │                     │ MITIGATED                  │
│   ↓                        │                     │   ↓                        │
│ POST_MORTEM (mandatory)    │                     │ CLOSED                     │
│   ↓                        │                     │                            │
│ CLOSED                     │                     │ Early closure:             │
│                            │                     │ OPEN/INVESTIGATING         │
│ Early closure:             │                     │  ↓ + Reason Form           │
│ OPEN/INVESTIGATING         │                     │ CLOSED                     │
│  ↓ + Reason Form           │                     │                            │
│ CLOSED (with reason)       │                     │                            │
└────────────────────────────┘                     └────────────────────────────┘
        ↓                                                       ↓
        └───────────────────────────┬───────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ CLOSURE                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ Method A: Normal Closure                                                   │
│   MITIGATED (or POST_MORTEM for P1/P2) → CLOSED                            │
│   No reason required                                                        │
│                                                                             │
│ Method B: Early Closure with Reason                                        │
│   OPEN or INVESTIGATING + Modal → CLOSED                                   │
│   Reason: DUPLICATE, FALSE_POSITIVE, SUPERSEDED, EXTERNAL, CANCELLED       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Differences

| | P1-P3 | P4-P5 | P1/P2 |
|---|---|---|---|
| Incident object | ✅ | ✅ | ✅ |
| Jira ticket | ✅ | ✅ | ✅ |
| Slack channel | ✅ | ❌ | ✅ |
| Post-mortem | ✅ | ❌ | ✅ |
| Form fields | Base | Base + team_routing + optional | Base |

---

## Implementation

See [incident-workflows.md](incident-workflows.md) for technical details on form and signals.

---

## Related

- **JIRA Sync**: [jira-integration.md](jira-integration.md)
- **Signals & Handlers**: [incident-workflows.md](incident-workflows.md) (technical deep-dive)

