# Unified Incident Opening Workflow

> **Date**: October 10, 2025
> **Status**: Current implementation

## 📋 Overview

The incident opening workflow in FireFighter now uses a **unified form** for all incident priorities (P1-P5). This simplified workflow eliminates the need for incident type selection (Step 3) and uses dynamic field visibility based on selected impacts.

## 🔄 Key Changes from Previous Workflow

### Before (Multiple Forms)
- **6 separate forms**: 1 critical form + 5 RAID forms (Customer, Seller, Internal, Documentation, Feature Request)
- **STEP 3 required**: Users had to select incident type for P4/P5
- **Static forms**: Each form had fixed fields regardless of impact selection

### After (Unified Form)
- **1 unified form**: `UnifiedIncidentForm` handles all priorities
- **STEP 3 hidden**: Automatically skipped since only one form type exists
- **Dynamic fields**: Fields show/hide based on selected impacts

---

## 📊 Complete Unified Workflow

### PART 1: All Incidents (P1-P5)

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
│   - priority_value < 4 → response_type = "critical" (P1-P3) │
│   - priority_value >= 4 → response_type = "normal" (P4-P5)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Priority/SLA Display (Response Type Block)         │
│ ─────────────────────────────────────────────────────────   │
│ Displays (non-editable):                                    │
│  • 🔴🟡🟢 Selected priority: P1/P2/P3/P4/P5 - Description    │
│  • ⏱️ SLA: 15min / 30min / 1h / 2days / 5days             │
│  • :gear: Process: Slack+Jira or Jira only                 │
│  • :pushpin: Selected impacts: [detailed list]             │
│  • :warning: Critical warning (P1-P3 only)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Select Incident Type                               │
│ ─────────────────────────────────────────────────────────   │
│ ⚡ AUTOMATICALLY HIDDEN ⚡                                   │
│                                                             │
│ Since len(INCIDENT_TYPES[response_type]) == 1,             │
│ this step is skipped entirely.                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Set Details (UnifiedIncidentFormSlack)             │
│ ─────────────────────────────────────────────────────────   │
│ COMMON Fields (always shown):                               │
│  • incident_category (GroupedModelChoiceField)              │
│  • environment (ModelMultipleChoiceField) - ALL priorities  │
│  • platform (MultipleChoiceField, default ALL) - ALL        │
│  • title (CharField, 10-128 chars)                          │
│  • description (TextField, 10-1200 chars)                   │
│  • priority (HiddenInput - auto-determined)                 │
│                                                             │
│ CONDITIONAL Fields (based on response_type):                │
│  • suggested_team_routing (P4/P5 ONLY)                      │
│                                                             │
│ DYNAMIC Fields (based on selected impacts):                 │
│  IF Customer Impact selected:                               │
│    • zendesk_ticket_id (optional)                           │
│  IF Seller Impact selected:                                 │
│    • seller_contract_id (optional)                          │
│    • is_key_account (boolean)                               │
│    • is_seller_in_golden_list (boolean)                     │
│    • zoho_desk_ticket_id (optional)                         │
│  IF Employee Impact selected:                               │
│    • (no additional fields)                                 │
│                                                             │
│ Note: Multiple impact types can be selected simultaneously  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Review & Submit                                    │
│ ─────────────────────────────────────────────────────────   │
│ Displays (based on response_type):                          │
│  IF Critical (P1-P3):                                       │
│    • :slack: Dedicated Slack channel will be created        │
│    • ~X responders will be invited                          │
│    • :jira_new: Associated Jira ticket will be created      │
│    • :pagerduty: (if outside office hours)                  │
│  IF Normal (P4-P5):                                         │
│    • :jira_new: A Jira ticket will be created               │
│    • (NO Slack channel, NO PagerDuty)                       │
│                                                             │
│ Button: "Create the incident"                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    [SUBMIT TRIGGERED]
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
   [CRITICAL P1-P3]                        [NORMAL P4-P5]
        ↓                                       ↓
_trigger_critical_incident_workflow    _trigger_normal_incident_workflow
        ↓                                       ↓
  Create Incident object                Determine Jira issue type
  Save impacts                          based on impacts:
  Create Slack channel                   - has_customer → create_issue_customer()
  Create Jira ticket                     - has_seller → create_issue_seller()
  Invite responders                      - else → create_issue_internal()
  Alert PagerDuty (if needed)           Create Jira ticket
                                        Save impacts
                                        Set watchers
                                        Alert Slack channels
```

---

## 🎯 Dynamic Field Visibility Logic

### Decision Tree for Field Display

```
START: User selects impacts in STEP 1
    ↓
Calculate priority_value → Determine response_type
    ↓
Build visible_fields list:
    ├─ ALWAYS include: title, description, incident_category,
    │                  environment, platform, priority
    ↓
IF response_type == "normal" (P4/P5):
    ├─ ADD: suggested_team_routing
    ↓
FOR EACH selected impact:
    ├─ IF customers_impact != NONE:
    │    └─ ADD: zendesk_ticket_id
    ├─ IF sellers_impact != NONE:
    │    └─ ADD: seller_contract_id, is_key_account,
    │             is_seller_in_golden_list, zoho_desk_ticket_id
    └─ IF employees_impact != NONE:
         └─ (no additional fields)
    ↓
Remove all fields NOT in visible_fields from form
    ↓
Display final form with only relevant fields
```

### Example Scenarios

**Scenario 1: P1 Critical with Customer Impact**
```
Response Type: critical
Impacts: customers_impact = HIGH

Visible Fields:
✅ title, description, incident_category
✅ environment (multiple), platform (multiple)
✅ priority (hidden)
✅ zendesk_ticket_id (customer impact)
❌ suggested_team_routing (not P4/P5)
❌ seller fields (no seller impact)
```

**Scenario 2: P4 Normal with Seller + Customer Impact**
```
Response Type: normal
Impacts: sellers_impact = MEDIUM, customers_impact = LOW

Visible Fields:
✅ title, description, incident_category
✅ environment (multiple), platform (multiple)
✅ priority (hidden)
✅ suggested_team_routing (P4/P5)
✅ zendesk_ticket_id (customer impact)
✅ seller_contract_id, is_key_account, etc. (seller impact)
```

**Scenario 3: P5 Normal with Employee Impact Only**
```
Response Type: normal
Impacts: employees_impact = LOW

Visible Fields:
✅ title, description, incident_category
✅ environment (multiple), platform (multiple)
✅ priority (hidden)
✅ suggested_team_routing (P4/P5)
❌ customer fields (no customer impact)
❌ seller fields (no seller impact)
```

---

## 🔧 Technical Implementation

### Core Files

#### 1. Unified Form (Django)
**File**: `src/firefighter/incidents/forms/unified_incident.py`

```python
class UnifiedIncidentForm(CreateIncidentFormBase):
    """Unified form for all incident types and priorities (P1-P5)."""

    def get_visible_fields_for_impacts(
        self, impacts_data: dict[str, ImpactLevel], response_type: str
    ) -> list[str]:
        """Determine which fields should be visible based on impacts."""
        # Returns list of field names that should be displayed

    def trigger_incident_workflow(
        self, creator: User, impacts_data: dict[str, ImpactLevel],
        response_type: str = "critical"
    ) -> None:
        """Trigger appropriate workflow based on response type."""
        if response_type == "critical":
            self._trigger_critical_incident_workflow(creator, impacts_data)
        else:
            self._trigger_normal_incident_workflow(creator, impacts_data)
```

#### 2. Slack Form Wrapper
**File**: `src/firefighter/slack/views/modals/opening/details/unified.py`

```python
class UnifiedIncidentFormSlack(UnifiedIncidentForm):
    """Slack version with Slack-specific field configurations."""

    def __init__(self, *args, impacts_data=None, response_type="critical", **kwargs):
        super().__init__(*args, **kwargs)
        self._impacts_data = impacts_data or {}
        self._response_type = response_type
        self._configure_field_visibility()  # Hide/show fields dynamically

    def _configure_field_visibility(self):
        """Remove fields that shouldn't be visible."""
        visible_fields = self.get_visible_fields_for_impacts(
            self._impacts_data, self._response_type
        )
        for field_name in list(self.fields.keys()):
            if field_name not in visible_fields:
                del self.fields[field_name]
```

#### 3. Configuration Registration
**File**: `src/firefighter/raid/apps.py`

```python
INCIDENT_TYPES["normal"] = {
    "normal": {
        "label": "Normal",
        "slack_form": OpeningUnifiedModal,
    },
}
# Since len() == 1, STEP 3 is automatically hidden
```

**File**: `src/firefighter/slack/views/modals/open.py`

```python
INCIDENT_TYPES["critical"] = {
    "critical": {
        "label": "Critical",
        "slack_form": OpeningUnifiedModal,
    },
}
# Same unified form used for both critical and normal
```

---

## 📌 Key Benefits

### 1. Simplified User Experience
- **No more incident type selection** for P4/P5 incidents
- **Fewer steps** in the workflow (4 instead of 5)
- **Contextual fields** only show what's relevant

### 2. Reduced Code Complexity
- **1 form instead of 6**: `UnifiedIncidentForm` replaces all previous forms
- **Single source of truth**: All incident creation logic in one place
- **Easier maintenance**: Changes apply to all incident types

### 3. Flexible Field Management
- **Dynamic visibility**: Fields adapt to user selections
- **Multiple impacts**: Can combine customer + seller impacts
- **Consistent behavior**: Same form structure for all priorities

### 4. Preserved Functionality
- ✅ All Jira ticket creation logic preserved
- ✅ All Slack notifications preserved
- ✅ All validation rules preserved
- ✅ All workflow integrations preserved

---

## 🔄 Migration from Old Workflow

### Removed Components

| Component | Status | Replacement |
|-----------|--------|-------------|
| `CreateNormalIncidentFormBase` | ❌ Deleted | `UnifiedIncidentForm` |
| `CreateNormalCustomerIncidentForm` | ❌ Deleted | `UnifiedIncidentForm` |
| `CreateRaidSellerForm` | ❌ Deleted | `UnifiedIncidentForm` |
| `CreateRaidInternalForm` | ❌ Deleted | `UnifiedIncidentForm` |
| `CreateRaidDocumentationForm` | ❌ Deleted | Not supported |
| `CreateRaidFeatureRequestForm` | ❌ Deleted | Not supported |
| `CreateIncidentFormSlack` (critical) | ❌ Deleted | `UnifiedIncidentFormSlack` |
| `raid/views/open_normal.py` | ❌ Deleted | `opening/details/unified.py` |

### Preserved Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `PlatformChoices` | `raid/forms.py` | Platform enum (FR/DE/IT/ES/UK/ALL/Internal) |
| `initial_priority()` | `raid/forms.py` | Get default priority |
| `process_jira_issue()` | `raid/forms.py` | Create Jira ticket + impacts |
| `get_business_impact()` | `raid/forms.py` | Calculate business impact |
| `alert_slack_new_jira_ticket()` | `raid/forms.py` | Send Slack notifications |
| `set_jira_ticket_watchers_raid()` | `raid/forms.py` | Add Jira watchers |
| `get_partner_alert_conversations()` | `raid/forms.py` | Find partner Slack channels |
| `get_internal_alert_conversations()` | `raid/forms.py` | Find internal Slack channels |

### Deprecated Features

**No longer supported**:
- ❌ Documentation Request incidents (P4/P5)
- ❌ Feature Request incidents (P4/P5)

**Rationale**: These were specialized types that can be handled through standard P4/P5 internal incidents.

---

## 🧪 Testing

Tests for the unified form should be added in:
```
tests/test_incidents/test_forms/test_unified_incident.py
```

Existing utility function tests remain in:
```
tests/test_raid/test_raid_forms.py
```

---

## 📚 Related Documentation

- [Project Architecture](overview.md)
- [JIRA Integration](jira-integration.md)
- [Incident Closure Workflow](incident-closure-workflow.md)
- [Incident Status Workflow](incident-status-workflow.md)
- [Previous Workflow State](incident-opening-workflow-complete.md) (Before unification)
