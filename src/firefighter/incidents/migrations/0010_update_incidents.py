from django.db import migrations, transaction

COMPONENT_MAPPING = {
    "Internal Messaging": "Helpcenter after sales",
    "Crisis Communication Room": "Other",
    "data-visitors": "Data Ingestion",
    "data-buyers": "Data Ingestion",
    "Seller Order": "Seller Admin and Experience",
    "Legacy": "Other",
    "Authentification": "Customer login & signup",
    "data-operations": "Data Ingestion",
    "Test Incident": "Other",
    "Legal": "Other",
}

# Global variable to store incidents with the previous component
# This will be used to restore the original component in case of rollback
INCIDENTS_BACKUP = {}


def forwards_func(apps, _schema_editor):
    Incident = apps.get_model("incidents", "Incident")
    Component = apps.get_model("incidents", "Component")
    with transaction.atomic():
        for old_component_name, new_component_name in COMPONENT_MAPPING.items():
            old_component = Component.objects.filter(name=old_component_name).first()
            incidents = Incident.objects.filter(component=old_component)
            ids = list(incidents.values_list("id", flat=True))
            if ids:
                INCIDENTS_BACKUP[old_component_name] = ids
                new_component = Component.objects.filter(name=new_component_name).first()
                incidents.update(component=new_component)


def backwards_func(apps, _schema_editor):
    Incident = apps.get_model("incidents", "Incident")
    Component = apps.get_model("incidents", "Component")
    with transaction.atomic():
        for old_component_name, ids in INCIDENTS_BACKUP.items():
            old_component = Component.objects.filter(name=old_component_name).first()
            Incident.objects.filter(id__in=ids).update(component=old_component)


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0009_update_sla"),  # Remplacez par la dernière migration précédente
    ]

    operations = [
        migrations.RunPython(forwards_func, backwards_func),
    ]
