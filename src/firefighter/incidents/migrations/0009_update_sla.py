from django.db import migrations


def update_priority_settings(apps, schema_editor):
    Priority = apps.get_model("incidents", "Priority")
    priorities_to_update = {
        "P1": ("02:00:00", True, True),
        "P2": ("04:00:00", True, True),
        "P3": ("1 day, 00:00:00", True, True),
        "P4": ("5 days, 00:00:00", True, True),
        "P5": ("10 days, 00:00:00", True, True),
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
