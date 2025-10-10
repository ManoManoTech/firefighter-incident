# Complete Incident Opening Workflow - Current State

> **Date**: October 10, 2025
> **Status**: Reference documentation BEFORE P4/P5 modification

## 📋 Overview

The incident opening workflow in FireFighter follows a multi-step process that varies according to the incident **priority** (P1 to P5).

## 🔍 Priority Determination Logic

Priority is **automatically calculated** from selected impacts:

- **P1-P3** → `response_type = "critical"` → Critical incident with dedicated Slack channel
- **P4-P5** → `response_type = "normal"` → Normal incident with only a Jira ticket

**Calculation**: `priority_value < 4 ? "critical" : "normal"`

---

## 📊 Complete Workflow by Priority

### PART 1: CRITICAL Incidents Workflow (P1/P2/P3)

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 0: Intro                                               │
│ - Welcome message                                           │
│ - Warning if recent incidents in the last hour              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Set Impacts (SelectImpactForm)                     │
│ ─────────────────────────────────────────────────────────   │
│ Dynamic fields for each ImpactType:                        │
│  • Business Impact (HIGH/MEDIUM/LOW/LOWEST/NO)              │
│  • Operational Impact (HIGH/MEDIUM/LOW/LOWEST/NO)           │
│  • Technical Impact (HIGH/MEDIUM/LOW/LOWEST/NO)             │
│                                                             │
│ → Auto-calculates priority_value and response_type         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Priority/SLA Display (Response Type Block)         │
│ ─────────────────────────────────────────────────────────   │
│ Displays (non-editable):                                    │
│  • 🔴 Selected priority: P1/P2/P3 - Description             │
│  • ⏱️ SLA: 15 min / 30 min / 1 hour                        │
│  • :gear: Process: :slack: Slack :jira_new: Jira ticket    │
│  • :pushpin: Selected impacts: [detailed list]             │
│  • :warning: Critical incidents are for emergency only      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Select Incident Type                               │
│ ─────────────────────────────────────────────────────────   │
│ 📝 "Then, select the type of issue / affected users"       │
│                                                             │
│ Dropdown with ONLY 1 option:                                │
│  • "Critical" → OpeningCriticalModal                        │
│                                                             │
│ ⚠️ This step is HIDDEN because len(INCIDENT_TYPES) == 1    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Set Details (CreateIncidentFormSlack)              │
│ ─────────────────────────────────────────────────────────   │
│ OpeningCriticalModal form:                                  │
│  • title (CharField, 10-128 chars)                          │
│  • description (TextField, 10-1200 chars)                   │
│  • incident_category (GroupedModelChoiceField)              │
│  • environment (ModelChoiceField)                           │
│  • priority (HiddenInput - already determined)              │
│                                                             │
│ ✅ NO "suggested_team_routing" field                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Review & Submit                                    │
│ ─────────────────────────────────────────────────────────   │
│ Displays:                                                   │
│  • :slack: Dedicated Slack channel will be created          │
│  • ~X responders will be invited                            │
│  • :jira_new: Associated Jira ticket will be created        │
│  • :pagerduty: (if outside office hours)                    │
│                                                             │
│ Button: "Create the incident"                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    [INCIDENT CREATED]
                            ↓
              [Slack Channel + Jira Ticket + PagerDuty]
```

---

### PART 2: NORMAL Incidents Workflow (P4/P5) - RAID MODULE

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 0: Intro                                               │
│ - Welcome message                                           │
│ - Warning if recent incidents in the last hour              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Set Impacts (SelectImpactForm)                     │
│ ─────────────────────────────────────────────────────────   │
│ Dynamic fields for each ImpactType:                        │
│  • Business Impact (HIGH/MEDIUM/LOW/LOWEST/NO)              │
│  • Operational Impact (HIGH/MEDIUM/LOW/LOWEST/NO)           │
│  • Technical Impact (HIGH/MEDIUM/LOW/LOWEST/NO)             │
│                                                             │
│ → Auto-calculates priority_value=4 or 5 and response_type="normal" │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Priority/SLA Display (Response Type Block)         │
│ ─────────────────────────────────────────────────────────   │
│ Displays (non-editable):                                    │
│  • 🟡/🟢 Selected priority: P4/P5 - Description             │
│  • ⏱️ SLA: 2 days / 5 days                                 │
│  • :gear: Process: :jira_new: Jira ticket                  │
│  • :pushpin: Selected impacts: [detailed list]             │
│  • (NO "critical incidents" warning)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Select Incident Type ⚠️ IMPORTANT STEP             │
│ ─────────────────────────────────────────────────────────   │
│ 📝 "Then, select the type of issue / affected users"       │
│                                                             │
│ Dropdown with 5 OPTIONS (defined in raid/apps.py):         │
│  • "Customer"              → OpeningRaidCustomerModal       │
│  • "Seller"                → OpeningRaidSellerModal         │
│  • "Internal"              → OpeningRaidInternalModal       │
│  • "Documentation request" → OpeningRaidDocumentationModal  │
│  • "Feature request"       → OpeningRaidFeatureRequestModal │
│                                                             │
│ ✅ This step is VISIBLE because len(INCIDENT_TYPES) > 1    │
└─────────────────────────────────────────────────────────────┘
                            ↓
           ┌────────────────┴────────────────┐
           ↓                                  ↓
    [CUSTOMER/SELLER/INTERNAL]     [DOCUMENTATION/FEATURE REQUEST]
           ↓                                  ↓
┌─────────────────────────────┐   ┌─────────────────────────────┐
│ STEP 4a: Set Details        │   │ STEP 4b: Set Details        │
│ (CreateNormal...FormSlack)  │   │ (CreateRaid...FormSlack)    │
│ ─────────────────────────── │   │ ─────────────────────────── │
│ COMMON Fields:              │   │ COMMON Fields:              │
│ • incident_category         │   │ • incident_category         │
│ • platform (FR/DE/IT/ES/UK) │   │ • platform (FR/DE/IT/ES/UK) │
│ • title (10-128 chars)      │   │ • title (10-128 chars)      │
│ • description (10-1200)     │   │ • description (10-1200)     │
│ • suggested_team_routing ✅ │   │ • suggested_team_routing ✅ │
│ • priority (HiddenInput)    │   │ • priority (HiddenInput)    │
│                             │   │                             │
│ SPECIFIC Fields:            │   │ (No specific fields)        │
│ [If CUSTOMER]               │   │                             │
│ • zendesk_ticket_id         │   │                             │
│                             │   │                             │
│ [If SELLER]                 │   │                             │
│ • seller_contract_id        │   │                             │
│ • is_key_account (bool)     │   │                             │
│ • is_seller_in_golden_list  │   │                             │
│ • zoho_desk_ticket_id       │   │                             │
│                             │   │                             │
│ [If INTERNAL]               │   │                             │
│ (no additional fields)      │   │                             │
└─────────────────────────────┘   └─────────────────────────────┘
           ↓                                  ↓
           └────────────────┬────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Review & Submit                                    │
│ ─────────────────────────────────────────────────────────   │
│ Displays:                                                   │
│  • :jira_new: A Jira ticket will be created                 │
│  • (NO mention of Slack channel)                            │
│  • (NO mention of PagerDuty)                                │
│                                                             │
│ Button: "Create the incident"                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    [JIRA TICKET CREATED]
                            ↓
                  [Ticket in the feature team board]
```

---

## 🎯 Summary of Key Differences

| Aspect | P1/P2/P3 (Critical) | P4/P5 (Normal/RAID) |
|--------|---------------------|---------------------|
| **Process** | Slack + Jira + PagerDuty | Jira only |
| **STEP 3: Select Type** | **HIDDEN** (only 1 option) | **VISIBLE** (5 options) |
| **Feature Team** | ❌ NOT present | ✅ PRESENT in all forms |
| **Details Form** | `CreateIncidentFormSlack` | `CreateNormal...FormSlack` (5 variants) |
| **Specific Fields** | None | zendesk_ticket_id, seller_contract_id, etc. |
| **Jira Destination** | Critical incident ticket | Feature team board ticket |

---

## 📌 `suggested_team_routing` Field

### Definition
```python
# File: src/firefighter/raid/forms.py, line 82-86
suggested_team_routing = forms.ModelChoiceField(
    queryset=FeatureTeam.objects.only("name").order_by("name"),
    label="Feature Team or Train",
    required=True,
)
```

### Field Presence

| Incident Type | Present in form? |
|---------------|------------------|
| **P1/P2/P3 (Critical)** | ❌ NO |
| **P4/P5 - Customer** | ✅ YES |
| **P4/P5 - Seller** | ✅ YES |
| **P4/P5 - Internal** | ✅ YES |
| **P4/P5 - Documentation** | ✅ YES |
| **P4/P5 - Feature Request** | ✅ YES |

### Usage
The `suggested_team_routing` field is used to:
1. **Route the Jira ticket** to the correct team board
2. **Automatically assign** the ticket to the responsible team
3. **Notify** the concerned team members

---

## 🔧 Source Code References

### 1. Response Type Determination
**File**: `src/firefighter/slack/views/modals/open.py:437-439`
```python
# Default fallback: P1/P2/P3 = critical, P4/P5 = normal
response_type = cast("ResponseType", "critical" if priority_value < 4 else "normal")
open_incident_context["response_type"] = response_type
```

### 2. Incident Types Configuration
**File**: `src/firefighter/slack/views/modals/open.py:52-65`
```python
INCIDENT_TYPES: dict[ResponseType, dict[str, dict[str, Any]]] = {
    "critical": {
        "critical": {
            "label": "Critical",
            "slack_form": OpeningCriticalModal,
        },
    },
    "normal": {
        "normal": {
            "label": "Normal",
            "slack_form": OpeningCriticalModal,  # Overridden by RAID
        },
    },
}
```

**File**: `src/firefighter/raid/apps.py:32-53` (OVERRIDE at startup)
```python
INCIDENT_TYPES["normal"] = {
    "CUSTOMER": {
        "label": "Customer",
        "slack_form": OpeningRaidCustomerModal,
    },
    "SELLER": {
        "label": "Seller",
        "slack_form": OpeningRaidSellerModal,
    },
    "INTERNAL": {
        "label": "Internal",
        "slack_form": OpeningRaidInternalModal,
    },
    "DOCUMENTATION_REQUEST": {
        "label": "Documentation request",
        "slack_form": OpeningRaidDocumentationRequestModal,
    },
    "FEATURE_REQUEST": {
        "label": "Feature request",
        "slack_form": OpeningRaidFeatureRequestModal,
    },
}
```

### 3. STEP 3 Display Logic
**File**: `src/firefighter/slack/views/modals/open.py:258-290`
```python
@staticmethod
def get_select_incident_type_blocks(
    open_incident_context: OpeningData,
    incident_type_value: str | None,
) -> list[Block]:
    response_type = open_incident_context.get("response_type")
    if (
        response_type is None
        or response_type not in INCIDENT_TYPES
        or len(INCIDENT_TYPES[response_type]) == 1  # ← HIDE if only 1 option
    ):
        return []
    # ... displays dropdown with options
```

---

## 🎯 Conclusion

The current workflow works as follows:

1. **For P1/P2/P3**: Simplified workflow with 4 steps (intro, impacts, priority display, details)
   - No type selection (automatically hidden)
   - No feature team field
   - Creates Slack channel + Jira ticket

2. **For P4/P5**: Complete workflow with 5 steps (intro, impacts, priority display, **type selection**, details)
   - Mandatory incident type selection (Customer/Seller/Internal/Doc/Feature)
   - Feature team field **present in ALL forms**
   - Creates only a Jira ticket in the team board

**Current blocker**: STEP 3 "Select type" is NECESSARY for P4/P5 because it determines which form to display (Customer vs Seller vs Internal, etc.), each having different specific fields.
