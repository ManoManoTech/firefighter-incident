"""Merge the three Marketplace front-end categories into a single "Foundations".

The three teams behind `Mobile Apps`, `Spartacux Foundations` and `Web performance`
are now one team, tracked in the `FOUN` Jira project.

This migration is deliberately NON-DESTRUCTIVE, unlike `0011_update_incidents`:
the old categories keep every incident already filed against them, so historical
per-category counts and `IncidentCategoryManager.queryset_with_mtbf` stay
reproducible. They are only retired from the *create* pickers via
`enabled_create=False`; the update-status and close forms still offer them so
existing incidents keep rendering their own category.

The Slack usergroups and conversations of the three old categories are copied onto
`Foundations`. This is required, not cosmetic: `slack.signals.get_users` resolves
responders through `incident.incident_category.usergroups` / `.conversations`, so a
category with empty M2Ms would page nobody.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

NEW_CATEGORY_NAME = "Foundations"
NEW_CATEGORY_GROUP = "Marketplace"
# Fixed so `fixtures/incidents/incident_categories.json` targets the same row.
# Without it, `pdm run dev-env-setup` (migrate then loaddata) would end up with two
# categories named "Foundations": one per source, each with its own primary key.
NEW_CATEGORY_ID = "01292f09-b357-5c07-be96-754b9ea5922f"
RETIRED_CATEGORY_NAMES = [
    "Mobile Apps",
    "Spartacux Foundations",
    "Web performance",
]


def _get_new_category_order(IncidentCategory, group):  # noqa: N803
    """Reuse the lowest order of the categories being retired, so `Foundations`
    lands where they sat in the Marketplace list instead of at the bottom.
    """
    orders = list(
        IncidentCategory.objects.filter(
            group=group, name__in=RETIRED_CATEGORY_NAMES
        ).values_list("order", flat=True)
    )
    return min(orders) if orders else 0


def add_foundations_category(apps, _schema_editor):
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")
    Group = apps.get_model("incidents", "Group")

    try:
        group = Group.objects.get(name=NEW_CATEGORY_GROUP)
    except Group.DoesNotExist:
        logger.warning(
            "Group '%s' not found, skipping creation of '%s'.",
            NEW_CATEGORY_GROUP,
            NEW_CATEGORY_NAME,
        )
        return

    with transaction.atomic():
        _category, created = IncidentCategory.objects.get_or_create(
            name=NEW_CATEGORY_NAME,
            group=group,
            defaults={
                "id": NEW_CATEGORY_ID,
                "order": _get_new_category_order(IncidentCategory, group),
                "enabled_create": True,
            },
        )
        if created:
            logger.info("Created incident category '%s'.", NEW_CATEGORY_NAME)
        else:
            logger.info(
                "Incident category '%s' already exists, reusing it.", NEW_CATEGORY_NAME
            )


def copy_slack_links_to_foundations(apps, _schema_editor):
    """Copy the usergroup/conversation links of the retired categories onto
    `Foundations`, so incidents filed against it page the same people.
    """
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")
    try:
        UserGroup = apps.get_model("slack", "UserGroup")
        Conversation = apps.get_model("slack", "Conversation")
    except LookupError:
        logger.info("The 'slack' app is not installed, skipping Slack link copy.")
        return

    category = IncidentCategory.objects.filter(name=NEW_CATEGORY_NAME).first()
    if category is None:
        logger.warning(
            "Incident category '%s' not found, skipping Slack link copy.",
            NEW_CATEGORY_NAME,
        )
        return

    with transaction.atomic():
        for model, label in ((UserGroup, "usergroup"), (Conversation, "conversation")):
            if not hasattr(model, "incident_categories"):
                logger.warning(
                    "%s has no 'incident_categories' field yet, skipping.", label
                )
                continue
            linked = model.objects.filter(
                incident_categories__name__in=RETIRED_CATEGORY_NAMES
            ).distinct()
            for obj in linked:
                obj.incident_categories.add(category)
                logger.info(
                    "Linked %s '%s' to incident category '%s'.",
                    label,
                    obj.name,
                    NEW_CATEGORY_NAME,
                )


def unlink_slack_links_from_foundations(apps, _schema_editor):
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")
    try:
        UserGroup = apps.get_model("slack", "UserGroup")
        Conversation = apps.get_model("slack", "Conversation")
    except LookupError:
        return

    category = IncidentCategory.objects.filter(name=NEW_CATEGORY_NAME).first()
    if category is None:
        return

    with transaction.atomic():
        for model in (UserGroup, Conversation):
            if not hasattr(model, "incident_categories"):
                continue
            for obj in model.objects.filter(incident_categories=category):
                obj.incident_categories.remove(category)


def remove_foundations_category(apps, _schema_editor):
    """Delete only the row this migration created. Incidents are never repointed by
    the forward migration, so nothing can be left dangling here.
    """
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")

    category = IncidentCategory.objects.filter(name=NEW_CATEGORY_NAME).first()
    if category is None:
        return
    # `Incident.incident_category` is PROTECT, but `IncidentUpdate.incident_category`
    # is SET_NULL — deleting would silently blank those rows. Refuse either way.
    if category.incident_set.exists() or category.incidentupdate_set.exists():
        logger.warning(
            "Incident category '%s' is referenced by incidents, not deleting it.",
            NEW_CATEGORY_NAME,
        )
        return
    category.delete()
    logger.info("Deleted incident category '%s'.", NEW_CATEGORY_NAME)


def retire_merged_categories(apps, _schema_editor):
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")

    updated = IncidentCategory.objects.filter(
        name__in=RETIRED_CATEGORY_NAMES
    ).update(enabled_create=False)
    logger.info("Retired %s incident categories from the create forms.", updated)


def restore_merged_categories(apps, _schema_editor):
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")

    updated = IncidentCategory.objects.filter(
        name__in=RETIRED_CATEGORY_NAMES
    ).update(enabled_create=True)
    logger.info("Restored %s incident categories to the create forms.", updated)


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0035_incidentcategory_enabled_create"),
    ]

    operations = [
        migrations.RunPython(add_foundations_category, remove_foundations_category),
        migrations.RunPython(
            copy_slack_links_to_foundations, unlink_slack_links_from_foundations
        ),
        migrations.RunPython(retire_merged_categories, restore_merged_categories),
    ]
