import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def get_group_mappings() -> dict:
    """Returns the mapping table for updating existing groups."""
    return {
        "Platform": ("Platform", 8),
        "Visitors": ("Marketplace", 1),
        "Specialist Offer (Catalog/Seller)": ("Catalog", 4),
        "Operations": ("Operations", 6),
        "Money": ("Payment Operations", 5),
        "Security": ("Security", 10),
        "Corporate IT": ("Corporate IT", 11),
        "Other": ("Other", 12),
        "Data": ("Data", 9),
    }


def get_new_groups() -> dict:
    """Returns a dictionary of new groups to be created."""
    return {
        "Marketing & Communication": 2,
        "Seller": 3,
        "Finance": 7,
    }


def add_new_groups(apps, _schema_editor):
    Group = apps.get_model("incidents", "Group")
    new_groups = get_new_groups()

    for name, position in new_groups.items():
        try:
            logger.info(f"Creating new group: '{name}' with order {position}")
            new_group = Group(name=name, order=position)
            new_group.save()
        except Exception:
            logger.exception(f"Failed to create new group '{name}'.")


def remove_new_groups(apps, _schema_editor):
    Group = apps.get_model("incidents", "Group")
    new_group_names = get_new_groups().keys()

    for name in new_group_names:
        try:
            logger.info(f"Removing group: '{name}'")
            group = Group.objects.get(name=name)
            group.delete()
        except Exception:
            logger.exception(f"Group '{name}' does not exist, skipping removal.")


def update_groups(apps, _schema_editor):
    Group = apps.get_model("incidents", "Group")
    group_mappings = get_group_mappings()

    updated_count = 0

    for old_name, (new_name, position) in group_mappings.items():
        try:
            logger.info(f"Updating group: '{old_name}' to '{new_name}'")
            group = Group.objects.get(name=old_name)
            group.name = new_name
            group.order = position
            group.save()
            updated_count += 1
        except Exception:
            logger.exception(f"Group '{old_name}' does not exist, cannot proceed with updates.")


def revert_group_names(apps, _schema_editor):
    Group = apps.get_model("incidents", "Group")
    reverse_mappings = {new_name: old_name for old_name, (new_name, _) in get_group_mappings().items()}

    updated_count = 0

    for new_name, old_name in reverse_mappings.items():
        try:
            group = Group.objects.get(name=new_name)
            logger.info(f"Restoring group '{new_name}' back to '{old_name}'")
            group.name = old_name
            group.save()
            updated_count += 1
        except Exception:
            logger.exception(f"Group '{new_name}' does not exist, skipping restoration.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0005_enable_from_p1_to_p5_priority"),
    ]

    operations = [
        migrations.RunPython(add_new_groups, remove_new_groups),
        migrations.RunPython(update_groups, revert_group_names),
    ]
