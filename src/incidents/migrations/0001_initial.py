# Generated by Django 3.2.3 on 2021-05-25 15:48

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models

import incidents.models.severity


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Component",
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
                ("slack_groups", models.CharField(default="", max_length=128)),
                ("cachet_id", models.IntegerField(null=True)),
                ("on_call", models.SmallIntegerField(default=0)),
                ("description", models.TextField()),
                ("order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="Environment",
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
                ("name", models.CharField(max_length=128, unique=True)),
                ("description", models.CharField(max_length=128, unique=True)),
                ("order", models.IntegerField(default=0)),
                ("default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Group",
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
                ("description", models.TextField()),
                ("order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Incident",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("title", models.CharField(max_length=128)),
                ("description", models.TextField()),
                (
                    "_status",
                    models.IntegerField(
                        choices=[
                            (10, "Open"),
                            (20, "Investigating"),
                            (30, "Fixing"),
                            (40, "Fixed"),
                            (50, "Post Mortem"),
                            (60, "Closed"),
                        ],
                        db_column="status",
                        default=10,
                    ),
                ),
                ("cachet_id", models.IntegerField(null=True)),
                ("pagerduty_id", models.CharField(max_length=128, null=True)),
                ("slack_channel_id", models.CharField(max_length=128, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Severity",
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
                ("name", models.CharField(max_length=128, unique=True)),
                ("emoji", models.CharField(default="🔥", max_length=5)),
                ("description", models.CharField(max_length=128)),
                ("order", models.IntegerField(default=0)),
                ("default", models.BooleanField(default=False)),
                ("needs_postmortem", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "severities",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="User",
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
                ("email", models.CharField(max_length=128, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slack_id", models.CharField(max_length=128, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="IncidentUpdate",
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
                ("message", models.TextField()),
                (
                    "_status",
                    models.IntegerField(
                        choices=[
                            (10, "Open"),
                            (20, "Investigating"),
                            (30, "Fixing"),
                            (40, "Fixed"),
                            (50, "Post Mortem"),
                            (60, "Closed"),
                        ],
                        db_column="status",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "commander",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="commander_for",
                        to="incidents.user",
                    ),
                ),
                (
                    "communications_lead",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="communications_lead_for",
                        to="incidents.user",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="incidents.user",
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="incidents.incident",
                    ),
                ),
                (
                    "severity",
                    models.ForeignKey(
                        on_delete=models.SET(
                            incidents.models.severity.Severity.get_default
                        ),
                        to="incidents.severity",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="incident",
            name="commander",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="incidents.user",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="communications_lead",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="incidents.user",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="component",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="incidents.component",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="incidents.user",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="environment",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="incidents.environment",
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="severity",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="incidents.severity",
            ),
        ),
        migrations.AddField(
            model_name="component",
            name="group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="incidents.group",
            ),
        ),
    ]
