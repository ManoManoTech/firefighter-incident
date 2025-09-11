# Generated manually on 2025-08-19 - Add incident_categories fields to Slack models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0022_add_incident_category_fields"),
        ("slack", "0004_alter_usergroup_components"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="incident_categories",
            field=models.ManyToManyField(
                blank=True,
                help_text="Incident categories that are related to this conversation. When creating a new incident with one of these incident categories, members will be invited to the conversation.",
                to="incidents.incidentcategory",
            ),
        ),
        migrations.AddField(
            model_name="usergroup",
            name="incident_categories",
            field=models.ManyToManyField(
                blank=True,
                help_text="Incident created with this usergroup automatically add the group members to these incident categories.",
                related_name="usergroups",
                to="incidents.incidentcategory",
            ),
        ),
    ]
