# Generated manually on 2025-08-19 - Remove components fields from Slack models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("slack", "0006_copy_components_to_incident_categories"),
        ("incidents", "0024_remove_component_fields_and_model"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="conversation",
            name="components",
        ),
        migrations.RemoveField(
            model_name="usergroup",
            name="components",
        ),
    ]
