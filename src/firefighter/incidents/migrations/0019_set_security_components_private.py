import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def set_security_components_to_private(apps, schema_editor):
    """Set all components belonging to the Security group as private, except 'Bot management & rate limiting & WAF'."""
    Component = apps.get_model("incidents", "Component")
    Group = apps.get_model("incidents", "Group")

    try:
        security_group = Group.objects.get(name="Security")
        components = Component.objects.filter(group=security_group).exclude(
            name="Bot management & rate limiting & WAF"
        )

        updated_count = 0
        for component in components:
            if not component.private:
                logger.info(f"Setting component '{component.name}' to private")
                component.private = True
                component.save()
                updated_count += 1

        logger.info(f"Updated {updated_count} Security components to private")
    except Group.DoesNotExist:
        logger.warning("Security group not found, skipping migration")


def revert_security_components_to_public(apps, schema_editor):
    """Revert all components belonging to the Security group to public, except 'Bot management & rate limiting & WAF'."""
    Component = apps.get_model("incidents", "Component")
    Group = apps.get_model("incidents", "Group")

    try:
        security_group = Group.objects.get(name="Security")
        components = Component.objects.filter(group=security_group).exclude(
            name="Bot management & rate limiting & WAF"
        )

        updated_count = 0
        for component in components:
            if component.private:
                logger.info(f"Setting component '{component.name}' to public")
                component.private = False
                component.save()
                updated_count += 1

        logger.info(f"Reverted {updated_count} Security components to public")
    except Group.DoesNotExist:
        logger.warning("Security group not found, skipping reverse migration")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0018_update_impactlevel_names"),
    ]

    operations = [
        migrations.RunPython(
            set_security_components_to_private,
            revert_security_components_to_public
        ),
    ]
