# Generated manually on 2025-08-19 - Step 6: Make incident_category field required

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0024_remove_component_fields_and_model"),
        ("slack", "0007_remove_components_fields"),
    ]

    operations = [
        # Make incident_category field required (not null)
        migrations.AlterField(
            model_name="incident",
            name="incident_category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="incidents.incidentcategory",
            ),
        ),
    ]
