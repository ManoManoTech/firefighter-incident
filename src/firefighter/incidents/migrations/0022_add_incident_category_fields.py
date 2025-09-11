# Generated manually on 2025-08-19 - Step 3: Add incident_category fields (nullable initially)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0021_copy_component_data_to_incident_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="incident_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="incidents.incidentcategory",
            ),
        ),
        migrations.AddField(
            model_name="incidentupdate",
            name="incident_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="incidents.incidentcategory",
            ),
        ),
    ]
