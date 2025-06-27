# Changelog

Please check [Github releases](https://github.com/ManoManoTech/firefighter-incident/releases).

## [Unreleased] - 2025-06-27

### Changed

#### Slack UX Improvements - Remove Critical/Normal Button Selection

- **BREAKING**: Removed manual Critical/Normal button selection in Slack incident creation workflow
- **IMPROVED**: Automatic response type calculation based on impact priority:
  - P1-P3 incidents → Critical (Slack channel + Jira ticket)
  - P4-P5 incidents → Normal (Jira ticket only)
- **ENHANCED**: Streamlined user experience with one less manual step
- **FIXED**: Eliminated inconsistency between calculated priority and manual response type selection

#### Impact System Improvements (June 2025)

- **ENHANCED**: Updated impact types and level ordering for better clarity
- **ADDED**: New impact levels including "N/A" option for more granular selection
- **IMPROVED**: Impact level descriptions and display names
- **FIXED**: Handle mixed data types in impact descriptions (string IDs vs ImpactLevel objects)
- **IMPROVED**: Automatic fallback to initial state when no impacts are selected (all set to "N/A")
- **ENHANCED**: Better error handling for non-existent priority values

#### Component and Priority System Overhaul (May-June 2025)

- **ADDED**: 61+ new Slack usergroups automatically mapped to components
- **ENHANCED**: Updated priority labels and forms for better user experience
- **IMPROVED**: Priority display consistency between Critical (P1-P3) and Normal (P4-P5)
- **ADDED**: New components including "Data Tools" and "Catalog Access"
- **MIGRATED**: Existing incidents to new component structure
- **UPDATED**: Component labels from "Components" to "Issue categories" in navigation
- **FIXED**: SLA and business impact calculations during incident creation

#### Test Environment Configuration

- **ADDED**: Test mode configuration for environments without Slack usergroups
- **IMPROVED**: Automatic incident creator invitation (works with any Slack user ID)
- **ENHANCED**: Configurable Slack usergroup invitations via `ENABLE_SLACK_USERGROUPS` setting

### Technical Details

#### Files Modified

- `src/firefighter/slack/views/modals/open.py`:
  - Removed `_build_response_type_blocks()` button generation
  - Maintained priority/SLA/process summary display
  - Removed action handlers for `incident_open_set_res_type_*`

- `src/firefighter/slack/views/modals/opening/select_impact.py`:
  - Added handling for "no impact selected" case (priority value 6)
  - Improved data type conversion for impact descriptions

- `src/firefighter/slack/signals/get_users.py`:
  - Added test mode detection for Slack usergroup invitations
  - Configurable usergroup invitation skipping

#### Configuration

New environment variables for test environments:

```bash
TEST_MODE=True
ENABLE_SLACK_USERGROUPS=False
```

### Benefits

- **User Experience**: Reduced workflow steps from 4 to 3
- **Consistency**: Guaranteed alignment between calculated priority and process
- **Error Reduction**: Eliminated potential user selection mistakes
- **Testing**: Simplified testing across different Slack workspaces

### Migration Notes

- No database migrations required
- Backward compatible with existing incidents
- No API changes
- Existing integrations unaffected

## Major System Changes Since v0.0.2 (March 2025)

### Infrastructure and Build Improvements

- **ADDED**: Django components system with modern type annotations
- **ENHANCED**: PDM package management and dependency handling
- **IMPROVED**: CI/CD pipeline with better testing and build processes
- **UPDATED**: Pre-commit hooks and code quality tools

### Data Model Enhancements

- **REVAMPED**: Complete component and group system with CSV-based updates
- **ENHANCED**: Priority system from P1-P5 with clear Critical/Normal distinction
- **ADDED**: Advanced impact level system with business-specific categories
- **IMPROVED**: Incident categorization and classification system

### Database Migrations

- **ADDED**: Multiple migrations for component restructuring (`0005_enable_from_p1_to_p5_priority.py`)
- **UPDATED**: Group names and component mappings (`0006_update_group_names.py`, `0007_update_component_name.py`)
- **ENHANCED**: Impact level system with new levels and ordering (`0008_impact_level.py`)
- **MIGRATED**: Existing incidents to new component structure with data preservation

### Development and Testing

- **IMPROVED**: Schema override capabilities for customization
- **ENHANCED**: Fixture management and test data consistency
- **ADDED**: Local development support with ACT (GitHub Actions locally)
- **UPDATED**: Build and test workflows for reliability

### Configuration and Customization

- **ADDED**: Flexible schema configuration system
- **ENHANCED**: Component-to-Slack usergroup mapping automation
- **IMPROVED**: Business impact calculation algorithms
- **UPDATED**: Form validation and user interaction flows

<!-- Contribution is welcome to improve the release and changelog automation -->
