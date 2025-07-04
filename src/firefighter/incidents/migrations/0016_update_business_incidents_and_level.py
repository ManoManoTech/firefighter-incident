# Generated by Django 4.2.7 on 2023-12-04 11:09


import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def update_incidents(apps, _schema_editor):
    ImpactLevel = apps.get_model("incidents", "ImpactLevel")
    ImpactType = apps.get_model("incidents", "ImpactType")
    Incident = apps.get_model("incidents", "Incident")

    business_impact_type = ImpactType.objects.filter(value="business_impact").first()
    if not business_impact_type:
        logger.error("ImpactType 'business_impact' does not exist. Skipping incident update.")
        return

    md_impact_level = ImpactLevel.objects.filter(value="MD", impact_type=business_impact_type.id).first()
    if not md_impact_level:
        logger.error("ImpactLevel 'MD' for business_impact does not exist. Skipping incident update.")
        return

    for level_value in ["LT", "LO"]:
        old_impact_level = ImpactLevel.objects.filter(value=level_value, impact_type=business_impact_type.id).first()
        if not old_impact_level:
            logger.error(f"ImpactLevel '{level_value}' for business_impact does not exist. Skipping.")
            continue

        # Find incidents that have the old impact level through the impacts relationship
        incidents_with_old_level = Incident.objects.filter(impacts=old_impact_level.id)
        updated_count = 0

        for incident in incidents_with_old_level:
            # Remove the old impact level and add the new one if not already present
            incident.impacts.remove(old_impact_level)
            if not incident.impacts.filter(id=md_impact_level.id).exists():
                incident.impacts.add(md_impact_level)
            updated_count += 1

        logger.info(f"Updated {updated_count} incidents from impact_level '{level_value}' to 'MD' for business_impact.")


def remove_old_impact_levels(apps, _schema_editor):
    ImpactLevel = apps.get_model("incidents", "ImpactLevel")
    ImpactType = apps.get_model("incidents", "ImpactType")
    Impact = apps.get_model("incidents", "Impact")

    business_impact_type = ImpactType.objects.filter(value="business_impact").first()
    if not business_impact_type:
        logger.error("ImpactType 'business_impact' does not exist. Skipping impact level removal.")
        return

    md_impact_level = ImpactLevel.objects.filter(value="MD", impact_type=business_impact_type.id).first()
    if not md_impact_level:
        logger.error("ImpactLevel 'MD' for business_impact does not exist. Cannot update Impact objects.")
        return

    for level_value in ["LT", "LO"]:
        impact_level = ImpactLevel.objects.filter(value=level_value, impact_type=business_impact_type.id).first()
        if impact_level:
            # Update all Impact objects that reference this impact level
            impacts_to_update = Impact.objects.filter(impact_level=impact_level)
            updated_count = impacts_to_update.update(impact_level=md_impact_level)
            logger.info(f"Updated {updated_count} Impact objects from '{level_value}' to 'MD' for business_impact.")

            # Now safe to delete the impact level
            impact_level.delete()
            logger.info(f"Removed ImpactLevel '{level_value}' for business_impact.")
        else:
            logger.error(f"ImpactLevel '{level_value}' for business_impact not found.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0015_update_impact_level"),
    ]
    operations = [
        migrations.RunPython(update_incidents),
        migrations.RunPython(remove_old_impact_levels),
    ]
