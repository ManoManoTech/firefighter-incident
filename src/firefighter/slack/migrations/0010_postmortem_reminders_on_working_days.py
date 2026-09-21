"""Keep the post-mortem reminder Beat schedule on working days.

`slack.0009` created the schedule with `day_of_week="*"`, so the task also fired on Saturdays
and Sundays. The task now refuses to send outside office hours, but there is no point waking a
worker twice a weekend to do nothing either.

The hours are read back from whatever the schedule currently holds rather than hardcoded: the
`CrontabSchedule` is editable from the Django admin, and an operator who retimed the reminders
should keep their times. Only the days change. A new row is fetched or created instead of the
current one being edited in place, because a `CrontabSchedule` can be shared by several
`PeriodicTask`s and the others are none of our business.
"""

from django.db import migrations

TASK_NAME = "slack.send_postmortem_reminders"
WORKING_DAYS = "1-5"
EVERY_DAY = "*"


def _move_to_days(apps, day_of_week: str) -> None:
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    for periodic_task in PeriodicTask.objects.filter(task=TASK_NAME).select_related(
        "crontab"
    ):
        current = periodic_task.crontab
        if current is None or current.day_of_week == day_of_week:
            continue

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=current.minute,
            hour=current.hour,
            day_of_week=day_of_week,
            day_of_month=current.day_of_month,
            month_of_year=current.month_of_year,
            timezone=current.timezone,
        )
        periodic_task.crontab = schedule
        periodic_task.save(update_fields=["crontab"])


def restrict_to_working_days(apps, schema_editor):
    _move_to_days(apps, WORKING_DAYS)


def restore_every_day(apps, schema_editor):
    _move_to_days(apps, EVERY_DAY)


class Migration(migrations.Migration):
    dependencies = [
        ("slack", "0009_add_postmortem_reminder_periodic_task"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            restrict_to_working_days,
            reverse_code=restore_every_day,
        ),
    ]
