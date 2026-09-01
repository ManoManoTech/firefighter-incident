# Testing the Incident Process Reminders

This guide explains how to test the process reminders without waiting two days.

The reminders tell the Incident Commander that they own driving a mitigated incident through to
closure: completing the post-mortem when the priority requires one (P1/P2), submitting the key
events and closing otherwise (P3).

## The two delays

Both live on the **Priority**, next to `reminder_time` and `sla`, so they are editable per
priority in the Django admin - no environment variable, no deployment, no worker restart:

| Priority field | Default | Meaning |
| --- | --- | --- |
| `postmortem_reminder_time` | 2 days | Time after mitigation before the first reminder |
| `postmortem_reminder_repeat_time` | 2 days | Inactivity before the reminder is sent again. `0` reminds only once |

Do not confuse `postmortem_reminder_time` with the existing **`reminder_time`** on the same
model: that one drives the *other* reminder, the one nagging an **open** incident that has had no
`IncidentUpdate` for a while (task `slack.send_reminders`, every 5 minutes during office hours).

Anything that moves the incident - a new `IncidentUpdate`, a status change - restarts the repeat
clock. The first reminder is also announced in `#critical-incidents` (tag `tech_incidents`) for
P1/P2 production incidents; the repeats stay in the incident channel.

Where to edit: **Django admin → Incidents → Priorities → \<the priority\>**. Durations accept the
Django format, e.g. `2 00:00:00` for two days or `00:05:00` for five minutes.

## Prerequisites

1. Apply migrations:
```bash
cd src
pdm run python manage.py migrate incidents
pdm run python manage.py migrate slack
```

2. Have at least one incident in MITIGATED or POST_MORTEM status, P1 to P3.

## Method 1: Backdate + manual run (RECOMMENDED)

### Step 1: List eligible incidents

```bash
cd src
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders --list-only
```

The output lists the delays configured for each priority, and for each incident whether it needs
a post-mortem and who holds command.

### Step 2: Backdate an incident

```bash
# Backdate by 3 days, past the 2-day first delay
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py backdate_incident_mitigated 123 --days 3
```

Available options:

- `--days N`, `--hours N`, `--minutes N`: how far back to move `mitigated_at`. They add up, and
  default to 6 days when none is given. Use `--minutes` with lowered delays to rehearse in minutes.
- `--reset`: reset `mitigated_at` to the current time.

### Step 3: Run the reminder task

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

### Step 4: Verify in Slack

- In the incident channel: the reminder mentions the Commander by name.
- In `#critical-incidents`: only on the first reminder, and only for P1/P2 production incidents.

## Method 2: Accelerated cadence, locally

Lower the delays on the priority you are testing with, then work in minutes. Either in the admin,
or from a shell:

```python
from datetime import timedelta
from firefighter.incidents.models.priority import Priority

Priority.objects.filter(value=3).update(
    postmortem_reminder_time=timedelta(minutes=1),
    postmortem_reminder_repeat_time=timedelta(minutes=2),
)
```

```bash
cd src
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py backdate_incident_mitigated 123 --minutes 5

POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

Run the second command again after two minutes to see the **repeat** fire, then create an
`IncidentUpdate` on the incident and run it once more to see the repeat correctly suppressed.

## Method 3: Accelerated rehearsal in production

Everything the reminders read is database configuration, so a rehearsal needs no deployment and no
environment change. Three knobs, all reversible from the Django admin:

1. **Lower the delays** on the priority you rehearse with: `Incidents → Priorities → P3`, set
   `postmortem_reminder_time` to `00:01:00` and `postmortem_reminder_repeat_time` to `00:02:00`.
   Read on each task run, so it takes effect immediately - no worker restart.
2. **Speed up the schedule**: `Periodic tasks` → *Send post-mortem reminders for mitigated
   incidents*. Its crontab runs at 10:00 and 15:00 Europe/Paris. Point it at an interval schedule
   (e.g. every minute) for the duration of the test.
3. **Pick a test incident**: declare one in a channel of your own, move it to MITIGATED, then
   backdate it with `backdate_incident_mitigated <id> --minutes N`.

Lowering the delay on **one** priority keeps the rehearsal contained: every other priority keeps
its production cadence while you test.

Keep the blast radius small: the reminder posts in the incident channel and, for P1/P2 production
incidents, announces in `#critical-incidents`. To rehearse without touching that channel, use a
**P3** test incident (out of the announcement rule) or a non-PRD environment.

### Restoring after the rehearsal

- Put both delays back on the priority: `2 00:00:00` for each.
- Restore the periodic task to its `0 10,15 * * *` Europe/Paris crontab.
- `backdate_incident_mitigated <id> --reset`, then close the test incident.

## Method 4: Django shell

```bash
cd src
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py shell
```

```python
from datetime import timedelta
from django.utils import timezone
from firefighter.incidents.models.incident import Incident

incident = Incident.objects.get(id=123)
incident.mitigated_at = timezone.now() - timedelta(days=3)
incident.save(update_fields=["mitigated_at"])
print(f"Incident #{incident.id} backdated to {incident.mitigated_at}, commander: {incident.commander}")

from firefighter.slack.tasks.send_postmortem_reminders import send_postmortem_reminders
send_postmortem_reminders()
```

## Verifying reminders

1. **In the incident channel**:
     - Title "⏰ Incident process reminder ⏰"
     - How long the incident has been mitigated, and on a repeat, how long the process has been still
     - The Commander mentioned, with what is expected of them
     - Buttons to open the post-mortem (Confluence/Jira), "Update status" and "Update roles"
2. **In #critical-incidents** (first reminder, P1/P2 production only):
     - "⏰ Post-mortem reminder for incident #XXX", with the Commander in the fields
3. **In the `Message` table**:
     - A row with `ff_type = "ff_incident_postmortem_reminder_5days"` per reminder sent. The task
       reads the most recent one to know when it last reminded, so the repeat cadence depends on
       these rows being written. The task logs an error if a reminder is sent but not saved.

## Debugging

```bash
export DJANGO_LOG_LEVEL=DEBUG

POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py test_postmortem_reminders
```

## Resetting an incident after testing

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py backdate_incident_mitigated 123 --reset
```

## Testing the Celery periodic task

```bash
# Scheduler
cd src
celery -A firefighter.firefighter beat --loglevel=info

# Worker, in another terminal
celery -A firefighter.firefighter worker --loglevel=info
```

The task runs at 10 AM and 3 PM (Paris time) by default. To inspect what is configured:

```bash
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true \
ENABLE_JIRA=true ENABLE_RAID=true pdm run python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask
for task in PeriodicTask.objects.filter(task="slack.send_postmortem_reminders"):
    print(f"Task: {task.name}")
    print(f"Schedule: {task.crontab or task.interval}")
    print(f"Enabled: {task.enabled}")
```

The Celery task name stays `slack.send_postmortem_reminders`: it is stored in that `PeriodicTask`
row, so renaming it would leave Beat dispatching a task no worker registers.
