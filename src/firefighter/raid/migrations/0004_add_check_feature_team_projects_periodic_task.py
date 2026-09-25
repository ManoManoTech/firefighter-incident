from django.db import migrations

TASK_NAME = "raid.check_feature_team_projects"


def create_periodic_task(apps, schema_editor):
    """Check every Monday at 9:00 (Europe/Paris) that feature team Jira projects accept tickets."""
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="9",
        day_of_week="1",
        day_of_month="*",
        month_of_year="*",
        timezone="Europe/Paris",
    )
    PeriodicTask.objects.get_or_create(
        name="Check feature team Jira projects",
        defaults={
            "task": TASK_NAME,
            "crontab": schedule,
            "enabled": True,
            "description": "Log an error for each feature team whose Jira project is archived, deleted or closed to issue creation (Mondays at 9 AM)",
        },
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("raid", "0003_delete_raidarea"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, reverse_code=remove_periodic_task),
    ]
