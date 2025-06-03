import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

COMPONENT_SLACK_GROUPS = {
    "Controlling": ("S08UYJGJ9HB", "finance-controlling"),
    "Applications": ("S08V22ZJ6DQ", "corporate-it-applications"),
    "Gitlab": ("S090A6LQ0U8", "platform-gitlab"),
    "Seller Admin and Experience": ("S08UV261ZRU", "seller-seller-admin-and-experience"),
    "Revenue": ("S08V22ZPBBL", "finance-revenue"),
    "Catalog Exposition": ("S08VD2WE5ND", "catalog-catalog-exposition"),
    "Company reputation": ("S090A63V7FS", "marketing-communication-company-reputation"),
    "BO Catalog - Master Experience": ("S08VD2Y1DMF", "catalog-bo-catalog-master-experience"),
    "Customer service": ("S08UV2GB7UN", "operations-customer-service"),
    "Seller's invoices": ("S08VD38AFFB", "finance-sellers-invoices"),
    "Cart & funnel": ("S08V2N7PRN0", "marketplace-cart-funnel"),
    "Data Ingestion": ("S08UYJHEFEH", "data-data-ingestion"),
    "Refunds": ("S08UM14D3LP", "payment-operations-refunds"),
    "Data Analytics": ("S08V2NNDG9J", "data-data-analytics"),
    "Mobile Apps": ("S08UV20CL6S", "marketplace-mobile-apps"),
    "Navigation & Product discovery": ("S08UYHZFFD3", "marketplace-navigation-product-discovery"),
    "Helpcenter after sales": ("S08UU3SHQTV", "operations-helpcenter-after-sales"),
    "CDN": ("S08UM12RNTZ", "platform-cdn"),
    "Customer's invoices": ("S08UYJGELJH", "finance-customers-invoices"),
    "Returns": ("S08UYJHDNQM", "operations-returns"),
    "Inventory": ("S08V2NNLW3W", "operations-inventory"),
    "Loyalty and coupons": ("S08V230H1V0", "payment-operations-loyalty-and-coupons"),
    "Seller Services": ("S08UM0SJ66T", "seller-seller-services"),
    "Spinak": ("S08UYJGRTE1", "platform-spinak"),
    "Data Tools": ("S08V2NPFDPE", "data-data-tools"),
    "Product Management": ("S08UYJ5GU93", "catalog-product-management"),
    "Compromised laptop / server": ("S08UU3T6H51", "security-compromised-laptop-server"),
    "Catalog Performance": ("S08V22QDHJ6", "catalog-catalog-performance"),
    "Spartacux Foundations": ("S08UYHZH97X", "marketplace-spartacux-foundations"),
    "Stolen account(s) or IT materials": ("S08UU3TFJ3D", "security-stolen-accounts-or-it-materials"),
    "MM Fulfillment": ("S08VD371F0R", "operations-mm-fulfillment"),
    "HUB Integrators": ("S08UM0SSNNB", "seller-hub-integrators"),
    "Exploited vulnerability": ("S08V2NPD084", "security-exploited-vulnerability"),
    "Commercial Animation": ("S08V2N6UA3E", "marketplace-commercial-animation"),
    "Cloud Infrastructure": ("S08UYJJ01HB", "platform-cloud-infrastructure"),
    "Tracking": ("S08UYHZPSTX", "marketplace-tracking"),
    "Data Warehouse": ("S08UYJHRWQ5", "data-data-warehouse"),
    "Infra - System": ("S08UV2H5WDC", "corporate-it-infra-system"),
    "VAT": ("S090A6LGGV6", "finance-vat"),
    "Web performance": ("S090A63K124", "marketplace-web-performance"),
    "Payouts to seller": ("S090A6M61A4", "payment-operations-payouts-to-seller"),
    "Seller Catalog and Offer Management": ("S08UV261CHL", "seller-seller-catalog-and-offer-management"),
    "Other": ("S08V22Z8S58", "other-other"),
    "Network": ("S090A6M3B7S", "corporate-it-network"),
    "Bot management & rate limiting & WAF": ("S090A6M8740", "security-bot-management-rate-limiting-waf"),
    "Customer login & signup": ("S08V22H38AE", "marketplace-customer-login-signup"),
    "Delivery experience": ("S08V2NP1E5A", "operations-delivery-experience"),
    "Accounting": ("S08VD37CJBT", "finance-accounting"),
    "Traffic acquisition": ("S08UU3BNPPV", "marketing-communication-traffic-acquisition"),
    "Payment": ("S08UM13DTFH", "payment-operations-payment"),
    "Data leak": ("S08UYJHBJPP", "security-data-leak"),
    "Offer (Price & Stock)": ("S08V2NCSPJ8", "catalog-offer-price-stock"),
    "Product Structure": ("S08V2NCNFV2", "catalog-product-structure"),
    "Catalog Access": ("S090A69J064", "catalog-catalog-access"),
    "Order management": ("S08UU3TRGJF", "operations-order-management"),
}


def update_components_slack_groups(apps, _):
    try:
        Component = apps.get_model("incidents", "Component")
        UserGroup = apps.get_model("slack", "UserGroup")
    except LookupError:
        logger.exception("The 'slack' app is not installed. Skipping migration.")
        return

    with transaction.atomic():
        for component_name, (user_group_id, user_group_name) in COMPONENT_SLACK_GROUPS.items():
            try:
                # Vérifier/créer le SlackUserGroup
                user_group, _ = UserGroup.objects.get_or_create(
                    name=user_group_name
                )
                # Si le slack_group_id a changé, le mettre à jour
                if user_group.usergroup_id != user_group_id:
                    user_group.usergroup_id = user_group_id
                    user_group.handle = user_group_name
                    user_group.save()

                # Vérifier/créer le Component
                component = Component.objects.get(name=component_name)
                if not component:
                    logger.error(f"Component '{component_name}' n'existe pas.")
                    continue

                # Lier le Component au SlackUserGroup via la relation du UserGroup
                if not hasattr(user_group, "components"):
                    logger.error(f"UserGroup '{user_group_name}' n'a pas d'attribut 'components'.")
                    continue

                if not user_group.components.filter(id=component.id).exists():
                    user_group.components.add(component)
                    logger.info(f"Component '{component_name}' ajouté au SlackUserGroup '{user_group_name}'")
            except Exception:
                logger.exception(f"Failed to update component: '{component_name}'.")


def ensure_firefighters_user_group(apps, _):
    try:
        Component = apps.get_model("incidents", "Component")
        UserGroup = apps.get_model("slack", "UserGroup")
    except LookupError:
        logger.exception("The 'slack' app is not installed. Skipping Firefighters user group check.")
        return

    try:
        firefighters_group = UserGroup.objects.get(name="firefighters")
    except UserGroup.DoesNotExist:
        logger.exception("UserGroup 'firefighters' does not exist.")
        return

    for component in Component.objects.all():
        if not hasattr(firefighters_group, "components"):
            logger.error("UserGroup 'firefighters' n'a pas d'attribut 'components'.")
            break
        if not firefighters_group.components.filter(id=component.id).exists():
            firefighters_group.components.add(component)
            logger.info(f"Component '{component.name}' ajouté au SlackUserGroup 'firefighters'.")


def cleanup_unused_slack_user_groups(apps, _):
    try:
        UserGroup = apps.get_model("slack", "UserGroup")
    except LookupError:
        logger.exception("The 'slack' app is not installed. Skipping user groups cleanup.")
        return

    valid_usergroup_ids = {v[0] for v in COMPONENT_SLACK_GROUPS.values()}

    for user_group in UserGroup.objects.all():
        if (
            user_group.usergroup_id not in valid_usergroup_ids
            and "firefighter" not in user_group.name.lower()
            and hasattr(user_group, "components")
        ):
            components_to_remove = list(user_group.components.all())
            if components_to_remove:
                user_group.components.clear()
                logger.info(
                    f"Removed components {[c.name for c in components_to_remove]} from SlackUserGroup '{user_group.name}'"
                    )


def delete_unused_slack_user_groups(apps, _):
    try:
        UserGroup = apps.get_model("slack", "UserGroup")
    except LookupError:
        logger.exception("The 'slack' app is not installed. Skipping user groups deletion.")
        return

    for user_group in UserGroup.objects.all():
        if "firefighters" in user_group.name.lower():
            continue
        if hasattr(user_group, "components") and user_group.components.count() == 0:
            logger.info(f"Deleting SlackUserGroup '{user_group.name}' (ID: {user_group.usergroup_id}) as it has no components.")
            user_group.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0013_add_missing_component"),
    ]

    operations = [
        migrations.RunPython(update_components_slack_groups),
        migrations.RunPython(ensure_firefighters_user_group),
        migrations.RunPython(cleanup_unused_slack_user_groups),
        migrations.RunPython(delete_unused_slack_user_groups),
    ]
