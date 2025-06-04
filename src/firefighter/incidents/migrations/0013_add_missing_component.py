import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def get_new_components() -> dict:
    """
    Returns a dictionary of new components to be created.

    Each entry in the dictionary maps a component name to a tuple containing:
    - group_name: The name of the group the component belongs to.
    - slack_channel: The associated Slack channel for the component.

    Returns:
        dict: A mapping of component names to (group name, slack channel) tuples.
    """
    return {
        "Data Tools": ("Data", "impact-data-tools"),
        "Catalog Access": ("Catalog", "impact-catalog-access"),
    }


def add_new_components(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    Group = apps.get_model("incidents", "Group")
    new_components = get_new_components()

    for name, (group_name, _slack) in new_components.items():
        logger.info(f"Creating new component: '{name}' belonging to group '{group_name}'")
        try:
            group_instance = Group.objects.get(name=group_name)
            new_component = Component(name=name, group=group_instance)
            new_component.save()
        except Exception:
            logger.exception(f"Failed to create new group: '{group_name}'.")


def remove_new_components(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    new_component_names = get_new_components().keys()

    for name in new_component_names:
        try:
            component = Component.objects.get(name=name)
            logger.info(f"Removing component: '{name}'")
            component.delete()
        except Exception:
            logger.exception(f"Component '{name}' does not exist, skipping removal.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0012_alter_impactlevel"),
    ]

    operations = [
        migrations.RunPython(add_new_components, remove_new_components),
    ]
