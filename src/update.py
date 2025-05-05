import os
from turtle import pos
import django
from django.db.models import F, Count
import traceback

from firefighter.incidents.models.group import Group
from firefighter.incidents.models.component import Component
from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.user_group import UserGroup
import csv


# Ensure Django is set up before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firefighter.firefighter.settings")
django.setup()


def export_groups_to_csv(file_path="data/group_name_mapping.csv"):
    groups = Group.objects.all()
    with open(file_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["old_name", "new_name"])
        writer.writeheader()
        for group in groups:
            writer.writerow({"old_name": group.name, "new_name": ""})
    print(f"Exported {len(groups)} groups to {file_path}")

def export_components_to_csv(file_path="data/component_name_mapping.csv"):
    components = Component.objects.all()
    with open(file_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["old_name", "new_name"])
        writer.writeheader()
        for component in components:
            writer.writerow({"old_name": component.name, "new_name": ""})
    print(f"Exported {len(components)} components to {file_path}")

def update_group_names(file_path="data/mapping_groups.csv"):
    """
    Reads group name mappings from a CSV file and updates groups accordingly.
    If a group with old_name exists, it updates its name to new_name.
    If a group with old_name doesn't exist but new_name is provided, creates a new group.
    
    Args:
        file_path (str): Path to the CSV file containing the mappings
    """
    import csv
    
    with open(file_path, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        
        updated_count = 0
        skipped_count = 0
        created_count = 0
        
        # Increment the position of all existing groups to avoid conflicts
        Group.objects.update(order=F('order') + 10000000)
        
        for row in reader:
            old_name = row.get("old_name", "").strip()
            new_name = row.get("new_name", "").strip()
            position = row.get("position", "").strip()
            
            if not new_name:
                print(f"Skip '{old_name}' : empty new_name")
                skipped_count += 1
                continue

            try:
                group = Group.objects.get(name=old_name if old_name else new_name)
                if old_name and group.name != new_name:
                    print(f"Update: '{old_name}' to '{new_name}'")
                else:
                    print(f"Update: '{new_name}'")
                group.name = new_name
                group.order = int(position)
                group.save()
                updated_count += 1
            except Group.DoesNotExist:
                if Group.objects.get(name=new_name):
                    group = Group.objects.get(name=new_name)
                    group.name = new_name
                    group.order = int(position)
                    group.save()
                    updated_count += 1
                else:
                    print(f"Create: '{new_name}'")
                    new_group = Group(name=new_name, order=position)
                    new_group.save()
                    created_count += 1
    print(f"Finished processing {file_path}")
    print(f"Groups updated: {updated_count}")
    print(f"Groups created: {created_count}")
    print(f"Entries skipped: {skipped_count}")
  
def update_component_names(file_path="data/mapping_components.csv"):
    """
    Reads component name mappings from a CSV file and updates components accordingly.
    If a component with old_name exists, it updates its name to new_name.
    If a component with old_name doesn't exist but new_name is provided, it logs a message about creating a new component.
    
    Args:
        file_path (str): Path to the CSV file containing the mappings
    """

    with open(file_path, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        updated_count = 0
        skipped_count = 0
        created_count = 0

        for row in reader:
            old_name = row["old_name"]
            new_name = row["new_name"]
            group = row["group"]
            # slack = row["slack"]
            
            if not group:
                print(f"Skip '{old_name}', no group")
                skipped_count += 1
                continue
            if not new_name:
                print(f"Skipping row with empty new_name for '{old_name}'")
                skipped_count += 1
                continue

            try:
                group_instance = Group.objects.get(name=group)
                component = Component.objects.get(name=old_name if old_name else new_name)
                if old_name and component.name != new_name:
                    print(f"Update: '{old_name}' to '{new_name}'")
                else:
                    print(f"Update: '{new_name}'")
                component.name = new_name
                component.group = group_instance
                component.save()
                updated_count += 1
            except Group.DoesNotExist:
                print(f"Skip: '{new_name}' | '{group}' does not exist.")
                skipped_count += 1
                continue
            except Component.DoesNotExist:
                if Component.objects.get(name=new_name):
                    print(f"Update: '{new_name}' already exists. Updating its group and order.")
                    existing_component = Component.objects.get(name=new_name)
                    existing_component.group = group_instance
                    existing_component.order = int(row.get("order", existing_component.order))
                    existing_component.save()
                    updated_count += 1
                else:
                    component = Component.objects.get(name=new_name)
                    print(f"Create: '{new_name}'")
                    max_order = Component.objects.aggregate(max_order=Count('order'))['max_order'] or 0
                    new_component = Component(name=new_name, group=group_instance, order=max_order + 1)
                    new_component.save()
                    created_count += 1
            except Exception as e:
                print(f"Erreur : {str(e)}")
                print("Traceback complet :")
                traceback.print_exc()
                skipped_count += 1
                continue

    print(f"Finished processing {file_path}")

def export_unmapped_components():
    """
    Exports components that are present in the database but not in the mapping file's new_name column to a CSV file.
    """

    mapped_new_names = set()
    with open("data/mapping_components.csv", mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if row["new_name"]:
                mapped_new_names.add(row["new_name"].strip())

    unmapped_components = Component.objects.exclude(name__in=mapped_new_names)

    with open("data/old_components_unmapped.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["name", "group", "order", "incidents"])
        writer.writeheader()
        for component in unmapped_components:
            writer.writerow({
                "name": component.name,
                "group": component.group.name if component.group else "",
                "incidents": Incident.objects.filter(component=component).count()
            })

    print(f"Exported {len(unmapped_components)}")

def export_unmapped_groups():
    """
    Exports groups that are present in the database but not in the mapping file's new_name column to a CSV file.
    """

    mapped_new_names = set()
    with open("data/mapping_groups.csv", mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if row.get("new_name", "").strip():
                mapped_new_names.add(row["new_name"].strip())

    unmapped_groups = Group.objects.exclude(name__in=mapped_new_names)

    with open("data/old_groups_unmapped.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["name", "order"])
        writer.writeheader()
        for group in unmapped_groups:
            writer.writerow({
                "name": group.name,
                "order": group.order,
            })

    print(f"Exported {len(unmapped_groups)} unmapped groups to old_groups_unmapped.csv")

def export_duplicates():
    """
    Exports duplicate groups and components based on their names to separate CSV files.
    For components, also includes the number of incidents associated with each duplicate.
    """
    duplicate_groups = (
        Group.objects.values("name")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    with open("data/duplicated_groups.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["id", "name", "count", "attached_components"])
        writer.writeheader()
        for group in duplicate_groups:
            group_instance = Group.objects.filter(name=group["name"]).first()
            attached_components_count = Component.objects.filter(group=group_instance).count() if group_instance else 0
            writer.writerow({
                "id": group_instance.id if group_instance else "N/A",
                "name": group["name"],
                "count": group["count"],
                "attached_components": attached_components_count,
            })

    print(f"Exported {len(duplicate_groups)} duplicated groups to duplicated_groups.csv")

    duplicate_components = (
        Component.objects.values("name")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    with open("data/duplicated_components.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["name", "count", "incidents"])
        writer.writeheader()
        for component in duplicate_components:
            incidents_count = Incident.objects.filter(component__name=component["name"]).count()
            writer.writerow({
                "name": component["name"],
                "count": component["count"],
                "incidents": incidents_count,
            })

    print(f"Exported {len(duplicate_components)} duplicated components to duplicated_components.csv")

def remove_duplicate_components():
    """
    Removes duplicate components by keeping only one instance of each name.
    Prefers to keep components with incidents, and deletes duplicates without incidents.
    """
    duplicate_components = (
        Component.objects.values("name")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    for component in duplicate_components:
        duplicates = Component.objects.filter(name=component["name"]).order_by("-id")
        keep = None
        for duplicate in duplicates:
            if keep is None:
                keep = duplicate
            else:
                if Incident.objects.filter(component=duplicate).exists():
                    keep = duplicate
                else:
                    duplicate.delete()

    print("Removed duplicate components, keeping one instance of each.")
    
def update_incident_components(file_path="data/mapping_incidents.csv"):
    """
    Reads incident component mappings from a CSV file and updates incidents accordingly.
    If an incident's component matches old_name, it updates it to the component matching new_name.

    Args:
        file_path (str): Path to the CSV file containing the mappings
    """

    with open(file_path, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        updated_count = 0
        skipped_count = 0

        for row in reader:
            old_component = row.get("old_component", "").strip()
            new_component = row.get("new_component", "").strip()

            if not old_component or not new_component:
                print(f"Skipping row with missing old_component or new_component: {row}")
                skipped_count += 1
                continue

            try:
                old_component = Component.objects.get(name=old_component)
                new_component = Component.objects.get(name=new_component)
                incidents_updated = Incident.objects.filter(component=old_component).update(component=new_component)
                updated_count += incidents_updated

                print(f"Updated {incidents_updated} incidents from '{old_component}' to '{new_component}'")
            except Component.DoesNotExist as e:
                print(f"Skipping row due to missing component: {old_component}")
                skipped_count += 1

            # Delete old components that are no longer associated with any incidents
            old_components = Component.objects.filter(name__in=[row["old_component"] for row in reader if row.get("old_component")])
            deleted_count = 0
            for component in old_components:
                if not Incident.objects.filter(component=component).exists():
                    print(f"Deleting old component: {component.name}")
                    component.delete()
                    deleted_count += 1

    print(f"Finished processing {file_path}")
    print(f"Incidents updated: {updated_count}")
    print(f"Entries skipped: {skipped_count}")
    print(f"Old components deleted: {deleted_count}")

def main() -> None:
    print(f"------ export_groups_to_csv ------")
    export_groups_to_csv()
    print(f"------ export_components_to_csv ------")
    export_components_to_csv()
    print(f"------ update_group_names ------")
    update_group_names()
    print(f"------ update_component_names ------")
    update_component_names()
    print(f"------ export_unmapped_groups ------")
    export_unmapped_groups()
    print(f"------ export_unmapped_components ------")
    export_unmapped_components()
    print(f"------ export_unmapped_components ------")
    export_duplicates()
    print(f"------ update_incident_components ------")
    update_incident_components()
    print(f"------ remove_duplicate_components ------")
    remove_duplicate_components()

def pdm_ff_update():
    """
    Entry point for the `pdm ff-update` command.
    """
    main()

if __name__ == "__main__":
    main()