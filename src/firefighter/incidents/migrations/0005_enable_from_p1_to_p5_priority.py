from django.db import migrations


def update_priority_settings(apps, schema_editor):
    Priority = apps.get_model("incidents", "Priority")
    priorities_to_update = ["P1", "P2", "P3", "P4", "P5"]

    Priority.objects.filter(name__in=priorities_to_update).update(
        enabled_create=False,
        enabled_update=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0004_incidentupdate_environment"),
    ]

    operations = [
        migrations.RunPython(update_priority_settings),
    ]
