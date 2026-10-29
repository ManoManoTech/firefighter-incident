"""Backfill the REJECTED status and the incident origin from the recorded closure reasons.

- Closed with a reason meaning "not a real incident" (duplicate, false alarm,
  superseded, cancelled): the incident and its closing update become REJECTED.
- Closed with the deprecated "external" reason: a real incident coming from a
  partner. It stays CLOSED with origin PARTNER; which partner is unknown.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

CLOSED = 60
REJECTED = 70
REJECTION_REASONS = ["duplicate", "false_positive", "superseded", "cancelled"]


def forwards(apps: Any, _schema_editor: Any) -> None:
    incident_model = apps.get_model("incidents", "Incident")
    incident_update_model = apps.get_model("incidents", "IncidentUpdate")

    rejected = incident_model.objects.filter(
        _status=CLOSED, closure_reason__in=REJECTION_REASONS
    )
    incident_update_model.objects.filter(incident__in=rejected, _status=CLOSED).update(
        _status=REJECTED
    )
    rejected.update(_status=REJECTED)

    incident_model.objects.filter(closure_reason="external").update(origin="partner")


def backwards(apps: Any, _schema_editor: Any) -> None:
    incident_model = apps.get_model("incidents", "Incident")
    incident_update_model = apps.get_model("incidents", "IncidentUpdate")

    incident_update_model.objects.filter(_status=REJECTED).update(_status=CLOSED)
    incident_model.objects.filter(_status=REJECTED).update(_status=CLOSED)
    incident_model.objects.filter(
        closure_reason="external", partner__isnull=True
    ).update(origin="internal")


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0039_rejected_status_and_partner_origin"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
