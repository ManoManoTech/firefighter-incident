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
        "Traffic acquisition": ("Marketing & Communication", "impact-traffic-acquisition"),
        "Company reputation": ("Marketing & Communication", "impact-company-reputation"),
        "Loyalty and coupons": ("Payment Operations", "impact-loyalty-coupons"),
        "Payouts to seller": ("Payment Operations", "impact-payouts-to-seller"),
        "Refunds": ("Payment Operations", "impact-refunds"),
        "Returns": ("Operations", "impact-returns"),
        "Customer service": ("Operations", "impact-customer-service"),
        "Inventory": ("Operations", "impact-inventory"),
        "VAT": ("Finance", "impact-vat"),
        "Seller's invoices": ("Finance", "impact-sellers-invoices"),
        "Customer's invoices": ("Finance", "impact-customers-invoices"),
        "Accounting": ("Finance", "impact-accounting"),
        "Revenue": ("Finance", "impact-revenue"),
        "Compromised laptop / server": ("Security", "impact-compromised-laptop-server"),
    }


def add_new_components(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    Group = apps.get_model("incidents", "Group")
    new_components = get_new_components()

    for name, (group_name, _slack) in new_components.items():
        if not Component.objects.filter(name=name).exists():
            logger.info(f"Creating new component: '{name}' belonging to group '{group_name}'")
            group_instance = None
            try:
                group_instance = Group.objects.get(name=group_name)
                # TODO: we have define component order here
                # TODO: should we had new migration that define order in function of alphabetical order ?
                new_component = Component(name=name, group=group_instance)
                new_component.save()
            except Group.DoesNotExist:
                logger.warning(f"Group '{group_name}' does not exist. Skipping creation for '{name}'.")
        else:
            logger.warning(f"Component '{name}' already exists in database.")


def remove_new_components(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    new_component_names = get_new_components().keys()

    for name in new_component_names:
        try:
            component = Component.objects.get(name=name)
            logger.info(f"Removing component: '{name}'")
            component.delete()
        except Component.DoesNotExist:
            logger.warning(f"Component '{name}' does not exist, skipping removal.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0007_update_component_name"),
    ]

    operations = [
        migrations.RunPython(add_new_components, remove_new_components),
    ]
