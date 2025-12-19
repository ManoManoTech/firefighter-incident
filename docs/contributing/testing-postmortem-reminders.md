# Testing Post-Mortem Reminders

This guide explains how to test the post-mortem reminder system without waiting 5 days.

## Prerequisites

1. Apply migrations:
```bash
cd src
pdm run python manage.py migrate incidents
pdm run python manage.py migrate slack
```

2. Have at least one incident in MITIGATED or POST_MORTEM status that requires a post-mortem (P1-P3)

## Method 1: Backdate + Manual Test (RECOMMENDED)

### Step 1: List eligible incidents

```bash
cd src
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders --list-only
```

### Step 2: Backdate an incident

If you have an incident (e.g., #123) that you want to test:

```bash
# Backdate by 6 days (to exceed the 5-day threshold)
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py backdate_incident_mitigated 123 --days 6
```

Available options:
- `--days N`: Number of days to backdate (default: 6)
- `--reset`: Reset to current time

### Step 3: Execute the reminder task

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

This command will:
1. List eligible incidents
2. Display their details (days since mitigation, etc.)
3. Send reminders in Slack

### Step 4: Verify in Slack

Check that messages were sent:
- In the incident channel
- In #critical-incidents (tag `tech_incidents`) if it's a P1-P3 production incident

## Method 2: Temporarily Modify the Delay

To test with a 5-minute delay instead of 5 days:

### Step 1: Modify the delay

Edit `src/firefighter/slack/tasks/send_postmortem_reminders.py`:

```python
# Line 30 - Change from:
POSTMORTEM_REMINDER_DAYS = 5

# To:
POSTMORTEM_REMINDER_DAYS = 0.0035  # ~5 minutes (5/1440 days)
```

### Step 2: Create an incident and move it to MITIGATED

Via the FireFighter interface, create a P1-P3 incident and move it to MITIGATED.

### Step 3: Wait 5 minutes and execute

```bash
# Wait 5 minutes, then:
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

### ⚠️ Important: Reset to original value

Don't forget to reset `POSTMORTEM_REMINDER_DAYS = 5` after your tests!

## Method 3: Via Django Console

```bash
cd src
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py shell
```

Then in the console:

```python
from datetime import timedelta
from django.utils import timezone
from firefighter.incidents.models.incident import Incident

# Find an incident
incident = Incident.objects.get(id=123)  # Replace 123 with your ID

# Backdate by 6 days
incident.mitigated_at = timezone.now() - timedelta(days=6)
incident.save(update_fields=['mitigated_at'])

print(f"Incident #{incident.id} backdated to {incident.mitigated_at}")

# Test the task
from firefighter.slack.tasks.send_postmortem_reminders import send_postmortem_reminders
send_postmortem_reminders()
```

## Verifying Reminders

After executing the task, verify:

1. **In the incident channel**:
   - Message with title "⏰ Post-mortem Reminder ⏰"
   - Buttons to open post-mortem (Confluence/Jira)
   - "Update status" button

2. **In #critical-incidents** (if P1-P3 production):
   - Message "⏰ Post-mortem reminder for incident #XXX"
   - Incident information
   - Links to channel and post-mortems

3. **In the Message table**:
   - A message with `ff_type = "ff_incident_postmortem_reminder_5days"`
   - This prevents duplicate sends

## Debugging

To see detailed logs:

```bash
# Increase log level
export DJANGO_LOG_LEVEL=DEBUG

# Then execute the test command
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

## Reset an Incident After Testing

To reset an incident to current time:

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py backdate_incident_mitigated 123 --reset
```

## Testing the Celery Periodic Task

To test that Celery executes the task automatically:

```bash
# Start Celery Beat (scheduler)
cd src
celery -A firefighter.firefighter beat --loglevel=info

# In another terminal, start the worker
celery -A firefighter.firefighter worker --loglevel=info
```

The task will automatically execute at 10 AM and 3 PM (Paris time).

To view configured periodic tasks:

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask
tasks = PeriodicTask.objects.filter(task='slack.send_postmortem_reminders')
for task in tasks:
    print(f"Task: {task.name}")
    print(f"Schedule: {task.crontab}")
    print(f"Enabled: {task.enabled}")
```
