# Generated manually on 2025-08-19 - Step 2: Copy Component data to IncidentCategory

from django.db import migrations


def copy_component_data_to_incident_category(apps, schema_editor):
    """Copy all data from Component to IncidentCategory"""
    Component = apps.get_model("incidents", "Component")
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")

    # Copy all components to incident categories with the same fields
    for component in Component.objects.all():
        IncidentCategory.objects.create(
            id=component.id,  # Keep same UUID
            name=component.name,
            description=component.description,
            order=component.order,
            private=component.private,
            deploy_warning=component.deploy_warning,
            created_at=component.created_at,
            updated_at=component.updated_at,
            group=component.group,
        )


def reverse_copy_component_data_to_incident_category(apps, schema_editor):
    """Reverse operation - copy IncidentCategory back to Component if needed"""
    Component = apps.get_model("incidents", "Component")
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")

    # This would only work if Component table still exists during rollback
    for incident_category in IncidentCategory.objects.all():
        Component.objects.create(
            id=incident_category.id,
            name=incident_category.name,
            description=incident_category.description,
            order=incident_category.order,
            private=incident_category.private,
            deploy_warning=incident_category.deploy_warning,
            created_at=incident_category.created_at,
            updated_at=incident_category.updated_at,
            group=incident_category.group,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0020_create_incident_category_model"),
    ]

    operations = [
        migrations.RunPython(
            copy_component_data_to_incident_category,
            reverse_copy_component_data_to_incident_category,
        ),
    ]
