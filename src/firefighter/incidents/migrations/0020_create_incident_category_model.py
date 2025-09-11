# Generated manually on 2025-08-19 - Step 1: Create IncidentCategory model

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0019_set_security_components_private"),
    ]

    operations = [
        migrations.CreateModel(
            name="IncidentCategory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "order",
                    models.IntegerField(
                        default=0,
                        help_text="Order of the incident category in the list. Should be unique per `Group`.",
                    ),
                ),
                (
                    "private",
                    models.BooleanField(
                        default=False,
                        help_text="If true, incident created with this incident category won't be communicated, and conversations will be made private. This is useful for sensitive incident categories. In the future, private incidents may be visible only to its members.",
                    ),
                ),
                (
                    "deploy_warning",
                    models.BooleanField(
                        default=True,
                        help_text="If true, a warning will be sent when creating an incident of high severity with this incident category.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        to="incidents.group"
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
            },
        ),
    ]
