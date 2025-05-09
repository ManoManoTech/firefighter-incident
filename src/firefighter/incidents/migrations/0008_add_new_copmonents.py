from django.db import migrations

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
        "Commercial Animation": ("Marketplace", "impact-commercial-animation"),
        "Mobile Apps": ("Marketplace", "impact-mobile-apps"),
        "Spartacux Foundations": ("Marketplace", "impact-spartacux-foundations"),
        "Product Discovery": ("Marketplace", "impact-nav-product-discovery"),
        "Tracking": ("Marketplace", "impact-tracking"),
        "Cart & funnel": ("Marketplace", "impact-cart-funnel"),
        "Customer Management": ("Marketplace", "impact-customer-login-signup"),
        "Performance": ("Marketplace", "impact-web-performance"),
        "Traffic acquisition": ("Marketing & Communication", "impact-traffic-acquisition"),
        "Company reputation": ("Marketing & Communication", "impact-company-reputation"),
        "HUB Integrators": ("Seller", "impact-hub-integrators"),
        "Seller Catalog and Offer Management": ("Seller", "impact-seller-catalog-offer-management"),
        "Seller Admin and Experience": ("Seller", "impact-seller-admin-experience"),
        "Seller Services": ("Seller", "impact-seller-services"),
        "Catalog Performance": ("Catalog", "impact-catalog-performance"),
        "Offer (Price & Stock)": ("Catalog", "impact-offer-price-stock"),
        "Back Office": ("Catalog", "impact-bo-catalog-master-experience"),
        "Product Management": ("Catalog", "impact-product-management"),
        "Product Structure": ("Catalog", "impact-product-structure"),
        "Catalog Exposition": ("Catalog", "impact-catalog-exposition"),
        "Catalog Access": ("Catalog", "impact-catalog-access"),
        "Payment": ("Payment Operations", "impact-payment"),
        "Loyalty and coupons": ("Payment Operations", "impact-loyalty-coupons"),
        "Payouts to seller": ("Payment Operations", "impact-payouts-to-seller"),
        "Refunds": ("Payment Operations", "impact-refunds"),
        "Order management": ("Operations", "impact-order-management"),
        "Delivery experience": ("Operations", "impact-delivery-experience"),
        "MM Fulfillment": ("Operations", "impact-mm-fulfillment"),
        "Returns": ("Operations", "impact-returns"),
        "Helpcenter after sales": ("Operations", "impact-helpcenter-after-sales"),
        "Customer service": ("Operations", "impact-customer-service"),
        "Inventory": ("Operations", "impact-inventory"),
        "VAT": ("Finance", "impact-vat"),
        "Seller's invoices": ("Finance", "impact-sellers-invoices"),
        "Customer's invoices": ("Finance", "impact-customers-invoices"),
        "Accounting": ("Finance", "impact-accounting"),
        "Revenue": ("Finance", "impact-revenue"),
        "Cloud Infrastructure": ("Platform", "impact-cloud-infrastructure"),
        "Spinak": ("Platform", "impact-spinak"),
        "CDN": ("Platform", "impact-cdn"),
        "Gitlab": ("Platform", "impact-gitlab"),
        "Data Ingestion": ("Data", "impact-data-ingestion"),
        "Data Tools": ("Data", "impact-data-tools"),
        "Data Warehouse": ("Data", "impact-data-warehouse"),
        "Data Analytics": ("Data", "impact-data-analytics"),
        "Bot management & rate limiting & WAF": ("Security", "impact-bot-management-rate-limiting-waf"),
        "Data leak": ("Security", "impact-data-leak"),
        "Exploited vulnerability": ("Security", "impact-exploited-vulnerability"),
        "Stolen account(s) or IT materials": ("Security", "impact-stolen-accounts-it-materials"),
        "Compromised laptop / server": ("Security", "impact-compromised-laptop-server"),
        "Network": ("Corporate IT", "impact-network"),
        "Infra - System": ("Corporate IT", "impact-infra-system"),
        "Applications": ("Corporate IT", "impact-applications"),
        "Other": ("Other", "impact-other"),
    }

def add_new_components(apps, schema_editor):
    Component = apps.get_model('incidents', 'Component')
    Group = apps.get_model('incidents', 'Group')
    new_components = get_new_components()

    for name, (group_name, slack) in new_components.items():
        if not Component.objects.filter(name=name).exists():
            print(f"Creating new component: '{name}' belonging to group '{group_name}'")
            group_instance = None
            try:
                group_instance = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                raise ValueError(f"Group '{group_name}' does not exist. Skipping creation for '{name}'.")
            # TODO: we have define component order here
            # TODO: should we had new migration that define order in function of alphabetical order ?
            new_component = Component(name=name, group=group_instance)
            new_component.save()
        else:
            raise ValueError(f"Component '{name}' already exists in database.")

def remove_new_components(apps, schema_editor):
    Component = apps.get_model('incidents', 'Component')
    new_component_names = get_new_components().keys()

    for name in new_component_names:
        try:
            component = Component.objects.get(name=name)
            print(f"Removing component: '{name}'")
            component.delete()
        except Component.DoesNotExist:
            print(f"Component '{name}' does not exist, skipping removal.")

class Migration(migrations.Migration):

    dependencies = [
        ('incidents', '0007_update_component_name'),
    ]

    operations = [
        migrations.RunPython(add_new_components, remove_new_components),
    ]
