
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
        # Marketplace
        ("Product Discovery", "Navigation & Product discovery", "impact-nav-product-discovery", "Marketplace"),
        ("User & Purchase", "Cart & funnel", "impact-cart-funnel", "Marketplace"),
        ("Customer Management", "Customer login & signup", "impact-customer-login-signup", "Marketplace"),
        ("Performance", "Web performance", "impact-web-performance", "Marketplace"),
        # Catalog
        ("Product Information", "Product Management", "impact-product-management", "Catalog"),
        ("Taxonomy", "Product Structure", "impact-product-structure", "Catalog"),
        ("Publication on website", "Catalog Exposition", "impact-catalog-exposition", "Catalog"),
        # Payment Operations
        ("Payment", "Payment", "impact-payment", "Payment Operations"),
        # Operations
        ("ManoFulfillment OPS", "MM Fulfillment", "impact-mm-fulfillment", "Operations"),
        ("Helpcenter", "Helpcenter after sales", "impact-helpcenter-after-sales", "Operations"),
        # Finance
        ("Finance Operations", "Controlling", "impact-controlling", "Finance"),
        # Platform
        ("Spinak", "Spinak", "impact-spinak", "Platform"),
        ("CDN", "CDN", "impact-cdn", "Platform"),
        ("Gitlab", "Gitlab", "impact-gitlab", "Platform"),
        # Data
        ("data-platform", "Data Ingestion", "impact-data-ingestion", "Data"),
        ("data-specialist-offer", "Data Warehouse", "impact-data-warehouse", "Data"),
        ("data-wbr", "Data Analytics", "impact-data-analytics", "Data"),
        # Security
        ("Security Misc", "Bot management & rate limiting & WAF", "impact-bot-management-rate-limiting-waf", "Security"),
        ("Attack", "Data leak", "impact-data-leak", "Security"),
        ("System Compromise", "Exploited vulnerability", "impact-exploited-vulnerability", "Security"),
        ("Personal Data Breach", "Stolen account(s) or IT materials", "impact-stolen-accounts-it-materials", "Security"),
    ]


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
        ("incidents", "0009_update_sla"),
    ]

    operations = [
        migrations.RunPython(update_component_names, revert_component_names),
    ]
