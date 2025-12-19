# Session: Post-mortem 5-day Reminders Implementation

**Date**: 2025-12-19
**Branch**: `feat/postmortem-5day-reminders`
**PR**: [#204](https://github.com/ManoManoTech/firefighter-incident/pull/204)
**Status**: ✅ Complete - Ready for merge

## Objective

Implement automated post-mortem reminders and notifications:
1. Send announcement to #critical-incidents when a PM is created (P1-P3 production incidents)
2. Send reminders 5 days after incident reaches MITIGATED status (both incident channel and #critical-incidents)
3. Run twice daily at 10 AM and 3 PM Paris time

## Implementation Summary

### New Features

1. **Post-mortem Creation Announcements**
   - Automatic notification to #critical-incidents (tag: `tech_incidents`) when PM is created
   - Only for P1-P3 production non-private incidents requiring post-mortem
   - Implemented via signal handler in `jira_app/signals/postmortem_created.py`

2. **5-day Overdue Reminders**
   - Celery periodic task checking incidents mitigated 5+ days ago
   - Sends reminders to incident channel and #critical-incidents (when applicable)
   - Runs at 10 AM and 3 PM Paris time
   - Prevents duplicates by tracking sent messages in database

3. **Testing Infrastructure**
   - Management command: `backdate_incident_mitigated` - Simulate old incidents
   - Management command: `test_postmortem_reminders` - Execute task manually with --list-only option
   - Documentation: `docs/contributing/testing-postmortem-reminders.md`

### Files Created

- `src/firefighter/slack/tasks/send_postmortem_reminders.py` - Celery task for 5-day reminders
- `src/firefighter/incidents/management/commands/backdate_incident_mitigated.py` - Testing tool
- `src/firefighter/incidents/management/commands/test_postmortem_reminders.py` - Testing tool
- `src/firefighter/incidents/migrations/0030_add_mitigated_at_field.py` - Database migration
- `src/firefighter/slack/migrations/0009_add_postmortem_reminder_periodic_task.py` - Celery periodic task setup
- `docs/contributing/testing-postmortem-reminders.md` - Testing guide

### Files Modified

- `src/firefighter/incidents/models/incident.py` - Added `mitigated_at` timestamp field
- `src/firefighter/jira_app/signals/postmortem_created.py` - Refactored with helper functions, added PM announcements
- `src/firefighter/slack/messages/slack_messages.py` - Added 3 new message classes
- `src/firefighter/slack/rules.py` - Added `should_publish_pm_in_general_channel()` rule
- `mkdocs.yml` - Added testing documentation to navigation

### Database Changes

1. **Incident model**: Added `mitigated_at` field (nullable DateTimeField)
   - Automatically populated via signal when status changes to MITIGATED
   - Used to calculate when reminders should be sent

2. **Celery Beat**: Created periodic task with CrontabSchedule
   - Schedule: 10 AM and 3 PM Paris time (hour="10,15")
   - Task: `slack.send_postmortem_reminders`

### Code Quality Improvements

- **Refactored** `postmortem_created_handler` to reduce complexity:
  - Extracted `_update_mitigated_at_timestamp()`
  - Extracted `_create_confluence_postmortem()`
  - Extracted `_create_jira_postmortem()`
  - Extracted `_publish_postmortem_announcement()`
- Made status filters explicit (using `_status__in` instead of range comparison)
- Added comprehensive type annotations for management commands
- All mypy and ruff checks passing

## Testing Performed

1. **Local Testing**:
   - Used existing `.env` database configuration
   - Backdated incident #12379 by 6 days using `backdate_incident_mitigated`
   - Executed `test_postmortem_reminders` command
   - Verified messages sent to:
     - Incident channel: C0A5HML1VPA
     - Critical incidents channel: C093217P747
   - Confirmed Message records created with proper `ff_type`

2. **Status Filter Testing**:
   - Verified both MITIGATED (40) and POST_MORTEM (50) statuses detected
   - SQL query shows correct `_status IN (40, 50)` filter

3. **CI/CD**:
   - All linting passing (mypy, ruff)
   - All mkdocs build checks passing
   - pre-commit.ci passing

## Commits

1. `e5a2b1f` - feat: add post-mortem reminders and critical-incidents notifications
2. `c7ad7ea` - refactor: make incident status filter more explicit
3. `b75bd1c` - fix: add testing-postmortem-reminders.md to mkdocs navigation

## Issues Encountered & Resolved

1. **Mkdocs strict build failure**
   - Issue: New documentation file not included in `mkdocs.yml` navigation
   - Fix: Added `testing-postmortem-reminders.md` to "Architecture & Design" section

2. **Status filter clarity**
   - Issue: User requested explicit filtering for MITIGATED and POST_MORTEM
   - Fix: Changed from range comparison to explicit list: `_status__in=[40, 50]`

## Configuration

### Celery Periodic Task

- **Task name**: "Send post-mortem reminders for mitigated incidents"
- **Task path**: `slack.send_postmortem_reminders`
- **Schedule**: CrontabSchedule
  - Minute: 0
  - Hour: 10,15
  - Timezone: Europe/Paris
- **Enabled**: Yes

### Constants

- `POSTMORTEM_REMINDER_DAYS = 5` in `send_postmortem_reminders.py`

### Message Types

- `ff_incident_postmortem_created_announcement` - PM creation in #critical-incidents
- `ff_incident_postmortem_reminder_5days` - 5-day reminder in incident channel
- `ff_incident_postmortem_reminder_5days_announcement` - 5-day reminder in #critical-incidents

## Documentation

Comprehensive testing guide available at `docs/contributing/testing-postmortem-reminders.md` covering:
- Three testing methods (backdate, modify delay, Django console)
- Step-by-step instructions with environment variables
- Verification steps
- Debugging tips
- Celery Beat testing

## Next Steps

- PR #204 ready for review and merge
- After merge: Monitor Celery periodic task execution at 10 AM and 3 PM
- Consider setting up monitoring/alerts for task execution failures

## Notes

- All documentation written in English per project standards
- Relative paths used in documentation (not absolute)
- Follows project behaviour protocols (quality checks, testing, etc.)
- Compatible with existing Slack workflow and message deduplication system
