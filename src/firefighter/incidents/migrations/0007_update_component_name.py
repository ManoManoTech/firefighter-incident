import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def get_component_mappings() -> list:
    """
    Returns a list of tuples for updating existing component names and their attributes.

    Each tuple contains:
        - old_name (str): The current name of the component.
        - new_name (str): The new name to assign to the component.
        - slack_channel (str): The associated Slack channel for the component.
        - group_name (str): The name of the group to which the component belongs.

    Returns:
        list: A list of tuples, each representing the details for a component update.
    """
    return [
        ("Commercial Animation (Mabaya cat. integration & ad request, ...)", "Commercial Animation", "impact-commercial-animation", "Marketplace"),
        ("Mobile Apps", "Mobile Apps", "impact-mobile-apps", "Marketplace"),
        ("Spartacux Foundations", "Spartacux Foundations", "impact-spartacux-foundations", "Marketplace"),
        ("Tracking", "Tracking", "impact-tracking", "Marketplace"),
        ("HUB Integrators", "HUB Integrators", "impact-hub-integrators", "Seller"),
        ("Seller Account and Feeds", "Seller Catalog and Offer Management", "impact-seller-catalog-offer-management", "Seller"),
        ("Toolbox", "Seller Admin and Experience", "impact-seller-admin-experience", "Seller"),
        ("Seller Services (Mabaya BO, Subscriptions, MF)", "Seller Services", "impact-seller-services", "Seller"),
        ("Catalog Performance", "Catalog Performance", "impact-catalog-performance", "Catalog"),
        ("Offer (Price, Stock)", "Offer (Price & Stock)", "impact-offer-price-stock", "Catalog"),
        ("Back Office", "BO Catalog - Master Experience", "impact-bo-catalog-master-experience", "Catalog"),
        ("Order Lifecycle", "Order management", "impact-order-management", "Operations"),
        ("Delivery Experience", "Delivery experience", "impact-delivery-experience", "Operations"),
        ("Cloud Infrastructure", "Cloud Infrastructure", "impact-cloud-infrastructure", "Platform"),
        ("Spinak", "Spinak", "impact-spinak", "Platform"),
        ("CDN", "CDN", "impact-cdn", "Platform"),
        ("Gitlab", "Gitlab", "impact-gitlab", "Platform"),
    ]


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


def update_component_names(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    Group = apps.get_model("incidents", "Group")
    component_mappings = get_component_mappings()

    updated_count = 0

    for old_name, new_name, _slack_channel, group_name in component_mappings:
        try:
            component = Component.objects.get(name=old_name)
            logger.info(f"Updating: '{old_name}' to '{new_name}'")
            component.name = new_name

            # WARN: this operaration is impossible to revert
            group_instance = Group.objects.get(name=group_name)
            component.group = group_instance
            component.save()
            updated_count += 1
        except Exception:
            logger.exception(f"Component '{old_name}' does not exist, cannot proceed with updates.")


def revert_component_names(apps, schema_editor):
    Component = apps.get_model("incidents", "Component")
    reverse_mappings = {new_name: old_name for old_name, new_name, _, _ in get_component_mappings()}

    updated_count = 0

    for new_name, old_name in reverse_mappings.items():

        try:
            component = Component.objects.get(name=new_name)
            logger.info(f"Restoring '{new_name}' back to '{old_name}'")
            component.name = old_name
            component.save()
            updated_count += 1
        except Exception:
            logger.exception(f"Component '{new_name}' does not exist, skipping restoration.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0006_update_group_names"),
    ]

    operations = [
        migrations.RunPython(update_component_names, revert_component_names),
        migrations.RunPython(add_new_components, remove_new_components),
    ]
