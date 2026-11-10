"""Remove the dead `Incident.closed_at` field from the Django state only.

`closed_at` was never written by FireFighter: the closing time of an incident is
carried by the IncidentUpdate that moves it to its final status.

This is the first step of a two-step removal. The column is left in the database
so that pods still running the previous release, which select every model column,
keep working while a rolling deployment applies this migration. The column is
nullable, so new rows inserted without it get NULL. A later migration drops it.
"""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0041_backfill_rejected_status_and_origin"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="incident",
                    name="closed_at",
                ),
            ],
            database_operations=[],
        ),
    ]
