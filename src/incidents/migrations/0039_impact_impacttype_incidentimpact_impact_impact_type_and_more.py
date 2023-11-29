# Generated by Django 4.1.7 on 2023-04-12 20:15

import django.db.models.deletion
from django.db import migrations, models


def add_impact_types(apps, schema_editor):
    ImpactType = apps.get_model("incidents", "ImpactType")
    impact_types_data = [
        {
            "name": "💰 BV Impact",
            "help_text": "Payment issues, loss of order funnel, etc...",
            "value": "business_impact",
        },
        {
            "name": "📦 Seller Impact",
            "help_text": "Ingestion, toolbox, etc...",
            "value": "sellers_impact",
        },
        {
            "name": "🛒 Customer Impact",
            "help_text": "Search, login, order tracking, etc...",
            "value": "customers_impact",
        },
        {
            "name": "👥 People Impact",
            "help_text": "Internal tooling, Slack, Gitlab, etc...",
            "value": "employees_impact",
        },
    ]

    for impact_type_data in impact_types_data:
        ImpactType.objects.create(
            name=impact_type_data["name"],
            help_text=impact_type_data["help_text"],
            value=impact_type_data["value"],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0038_alter_incident_severity"),
    ]

    operations = [
        migrations.CreateModel(
            name="Impact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "value",
                    models.CharField(
                        choices=[
                            ("NA", "❔ N/A"),
                            ("HI", "🔼 High"),
                            ("MD", "➡️ Medium"),
                            ("LO", "🔽 Low"),
                            ("NO", "0️⃣ None"),
                        ],
                        max_length=2,
                    ),
                ),
                ("details", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ImpactType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                ("help_text", models.CharField(max_length=128)),
                ("value", models.SlugField(unique=True)),
            ],
            options={
                "verbose_name_plural": "Impact Types",
            },
        ),
        migrations.CreateModel(
            name="IncidentImpact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "impact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="incidents.impact",
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="incidents.incident",
                    ),
                ),
            ],
            options={
                "verbose_name": "Incident impact",
                "verbose_name_plural": "Incident impacts",
            },
        ),
        migrations.AddField(
            model_name="impact",
            name="impact_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="incidents.impacttype"
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="impacts",
            field=models.ManyToManyField(
                through="incidents.IncidentImpact", to="incidents.impact"
            ),
        ),
        migrations.AddConstraint(
            model_name="impact",
            constraint=models.CheckConstraint(
                check=models.Q(("value__in", ["NA", "HI", "MD", "LO", "NO"])),
                name="incidents_impact_value_valid",
            ),
        ),
        migrations.RunPython(add_impact_types, migrations.RunPython.noop),
    ]
