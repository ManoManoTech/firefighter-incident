# Incident Workflow

> All priorities (P1-P5) follow the same workflow. Differences are in Slack channels and post-mortem requirements.

---

## Complete Workflow

```mermaid
graph TD
    A["📝 Form Submission<br/>Selects impacts"] --> B["✅ UnifiedIncidentForm<br/>Priority auto-determined"]

    B --> C["📌 Creates:<br/>Incident + Jira"]
    C --> D{Priority?}

    D -->|P1-P3| E["📱 Slack channel"]
    D -->|P4-P5| F["⊘ No Slack"]

    E --> G1["🔓 OPEN"]
    F --> G1

    G1 --> H1["🔍 INVESTIGATING"]
    G1 -->|Early closure<br/>+ Reason modal| CLOSED["✅ CLOSED"]

    H1 --> I1["🔧 MITIGATING"]
    H1 -->|Early closure<br/>+ Reason modal| CLOSED

    I1 --> J1{Post-Mortem?}

    J1 -->|P1/P2| K1["⚡ MITIGATED"]
    J1 -->|P3-P5| K2["⚡ MITIGATED"]

    K1 --> L1["📋 POST_MORTEM"]
    K2 --> CLOSED

    L1 --> CLOSED

    style A fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    style B fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    style C fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    style G1 fill:#FFB74D,stroke:#F57F17,stroke-width:2px,color:#000
    style H1 fill:#FFB74D,stroke:#F57F17,stroke-width:2px,color:#000
    style I1 fill:#FFB74D,stroke:#F57F17,stroke-width:2px,color:#000
    style K1 fill:#81C784,stroke:#388E3C,stroke-width:2px,color:#fff
    style K2 fill:#81C784,stroke:#388E3C,stroke-width:2px,color:#fff
    style L1 fill:#64B5F6,stroke:#1976D2,stroke-width:2px,color:#fff
    style CLOSED fill:#4CAF50,stroke:#2E7D32,stroke-width:3px,color:#fff
    style J1 fill:#9C27B0,stroke:#6A1B9A,stroke-width:2px,color:#fff
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

## Post-Mortem (PM) - P1/P2 Only

When incident reaches `MITIGATED` status (P1/P2 incidents):

```
User clicks "Create post-mortem" in Slack
    ↓
PostMortemManager checks enabled backends
    ├─ Confluence? → Create Confluence page
    └─ JIRA? → Create JIRA issue with templates
    ↓
Auto-assign to incident commander (if they have JIRA account)
    ↓
Notify Slack channel with link
    ↓
User manually completes PM (retrospective notes)
    ↓
User transitions incident: POST_MORTEM → CLOSED
```

**Deployment modes**:
- Confluence only (legacy)
- JIRA only (target)
- Both (migration/dual)

See [jira-postmortem.md](jira-postmortem.md) for configuration and troubleshooting.

---

## Related

- **JIRA Post-Mortem**: [jira-postmortem.md](jira-postmortem.md) - Configuration & setup
- **JIRA Sync**: [jira-integration.md](jira-integration.md) - Incident↔JIRA sync
- **Signals & Handlers**: [incident-workflows.md](incident-workflows.md) (technical deep-dive)
