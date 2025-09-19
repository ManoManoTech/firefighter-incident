from datetime import timedelta

from django.db import migrations


def update_priority_settings(apps, schema_editor):
    Priority = apps.get_model("incidents", "Priority")
    priorities_to_update = {
        "P1": (timedelta(hours=2), True, True),
        "P2": (timedelta(hours=4), True, True),
        "P3": (timedelta(days=1), True, True),
        "P4": (timedelta(days=5), True, True),
        "P5": (timedelta(days=10), True, True),
    }

    for name, (sla, enabled_create, enabled_update) in priorities_to_update.items():
        Priority.objects.filter(name=name).update(
            sla=sla,
            enabled_create=enabled_create,
            enabled_update=enabled_update,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0008_impact_level"),
    ]

    operations = [
        migrations.RunPython(update_priority_settings),
    ]
