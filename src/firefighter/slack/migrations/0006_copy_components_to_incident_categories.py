# Generated manually on 2025-08-19 - Copy component relationships to incident_categories

from django.db import migrations


def copy_components_to_incident_categories(apps, schema_editor):
    """Copy all component M2M relationships to incident_categories M2M relationships"""
    Conversation = apps.get_model("slack", "Conversation")
    UserGroup = apps.get_model("slack", "UserGroup")

    # Copy conversation components to incident_categories
    conversations_updated = 0
    for conversation in Conversation.objects.prefetch_related("components").all():
        # Copy all component relationships to incident_categories (same UUIDs)
        incident_category_ids = list(conversation.components.values_list("id", flat=True))
        conversation.incident_categories.set(incident_category_ids)
        if incident_category_ids:
            conversations_updated += 1

    # Copy usergroup components to incident_categories
    usergroups_updated = 0
    for usergroup in UserGroup.objects.prefetch_related("components").all():
        incident_category_ids = list(usergroup.components.values_list("id", flat=True))
        usergroup.incident_categories.set(incident_category_ids)
        if incident_category_ids:
            usergroups_updated += 1


def reverse_copy_components_to_incident_categories(apps, schema_editor):
    """Reverse: copy incident_categories relationships back to components"""
    Conversation = apps.get_model("slack", "Conversation")
    UserGroup = apps.get_model("slack", "UserGroup")

    # Copy conversation incident_categories back to components
    for conversation in Conversation.objects.prefetch_related("incident_categories").all():
        component_ids = list(conversation.incident_categories.values_list("id", flat=True))
        conversation.components.set(component_ids)

    # Copy usergroup incident_categories back to components
    for usergroup in UserGroup.objects.prefetch_related("incident_categories").all():
        component_ids = list(usergroup.incident_categories.values_list("id", flat=True))
        usergroup.components.set(component_ids)


class Migration(migrations.Migration):

    dependencies = [
        ("slack", "0005_add_incident_categories_fields"),
        ("incidents", "0023_populate_incident_category_references"),
    ]

    operations = [
        migrations.RunPython(
            copy_components_to_incident_categories,
            reverse_copy_components_to_incident_categories,
        ),
    ]
