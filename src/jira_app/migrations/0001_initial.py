# Generated by Django 4.2.3 on 2023-07-17 09:50

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_from_old_model(apps, schema_editor):
    OldJiraUser = apps.get_model("raid", "JiraUser")
    NewJiraUser = apps.get_model("jira_app", "JiraUser")

    new_jira_users = [
        NewJiraUser(id=old.id, user_id=old.user_id) for old in OldJiraUser.objects.all()
    ]
    NewJiraUser.objects.bulk_create(new_jira_users)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JiraUser",
            fields=[
                (
                    "id",
                    models.CharField(max_length=128, primary_key=True, serialize=False),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jira_user_new",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Jira user",
                "verbose_name_plural": "Jira users",
            },
        ),
        migrations.RunPython(
            copy_from_old_model, reverse_code=migrations.RunPython.noop
        ),
    ]
