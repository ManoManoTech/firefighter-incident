from django.db import migrations

SERVICE_USERNAME = "jira-webhook"
SERVICE_EMAIL = "jira-webhook@firefighter.invalid"


def create_jira_webhook_user(apps, schema_editor):
    User = apps.get_model("incidents", "User")
    User.objects.update_or_create(
        username=SERVICE_USERNAME,
        defaults={
            "email": SERVICE_EMAIL,
            "name": "Jira Webhook",
            "first_name": "Jira",
            "last_name": "Webhook",
            "bot": True,
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        },
    )


def delete_jira_webhook_user(apps, schema_editor):
    User = apps.get_model("incidents", "User")
    User.objects.filter(username=SERVICE_USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0032_disable_confluence_periodic_tasks"),
    ]

    operations = [
        migrations.RunPython(create_jira_webhook_user, delete_jira_webhook_user),
    ]
