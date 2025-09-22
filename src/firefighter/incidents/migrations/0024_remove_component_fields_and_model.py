# Generated manually on 2025-08-19 - Step 5: Remove component fields and model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0023_populate_incident_category_references"),
    ]

    operations = [
        # Remove the component foreign key fields
        migrations.RemoveField(
            model_name="incident",
            name="component",
        ),
        migrations.RemoveField(
            model_name="incidentupdate",
            name="component",
        ),
        # Remove the component model entirely
        migrations.DeleteModel(
            name="Component",
        ),
    ]
