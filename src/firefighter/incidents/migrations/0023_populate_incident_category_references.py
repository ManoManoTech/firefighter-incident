# Generated manually on 2025-08-19 - Step 4: Populate incident_category references from component

from django.db import migrations


def populate_incident_category_references(apps, schema_editor):
    """Copy component references to incident_category references"""
    Incident = apps.get_model("incidents", "Incident")
    IncidentUpdate = apps.get_model("incidents", "IncidentUpdate")

    # Update all incidents to point to the corresponding incident category
    incidents_updated = 0
    for incident in Incident.objects.select_related("component").all():
        if incident.component:
            # Find the corresponding incident category (same UUID)
            incident.incident_category_id = incident.component_id
            incident.save(update_fields=["incident_category"])
            incidents_updated += 1

    # Update all incident updates to point to the corresponding incident category
    updates_updated = 0
    for incident_update in IncidentUpdate.objects.select_related("component").all():
        if incident_update.component:
            incident_update.incident_category_id = incident_update.component_id
            incident_update.save(update_fields=["incident_category"])
            updates_updated += 1


def reverse_populate_incident_category_references(apps, schema_editor):
    """Reverse: copy incident_category references back to component references"""
    Incident = apps.get_model("incidents", "Incident")
    IncidentUpdate = apps.get_model("incidents", "IncidentUpdate")

    # Restore component references from incident_category references
    for incident in Incident.objects.select_related("incident_category").all():
        if incident.incident_category:
            incident.component_id = incident.incident_category_id
            incident.save(update_fields=["component"])

    for incident_update in IncidentUpdate.objects.select_related("incident_category").all():
        if incident_update.incident_category:
            incident_update.component_id = incident_update.incident_category_id
            incident_update.save(update_fields=["component"])


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0022_add_incident_category_fields"),
    ]

    operations = [
        migrations.RunPython(
            populate_incident_category_references,
            reverse_populate_incident_category_references,
        ),
    ]
