"""Link the `Foundations` incident category to its Slack usergroup.

`0036` created the `Foundations` category and copied the usergroup/conversation
links of the three categories it supersedes, so incidents filed against it
already page the right people. This migration points it at the single
consolidated usergroup instead.

The Slack usergroup is created by MagicDesk on request (we hold no Slack admin
token), so its ID is hardcoded here — the same approach as
`0014_update_components_slack_groups`, which pins 60+ usergroup IDs. It is
deliberately NOT declared in `infra/terraform/groups.yaml`: terraform does not
manage this group, and claiming it there would make the next `terraform apply`
fail on an already-existing handle.

The usergroups copied by `0036` are left linked. Unlinking them is a separate,
reversible decision to take only once this group is confirmed to page the right
people.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

CATEGORY_NAME = "Foundations"

# Slack usergroup ID, created by MagicDesk on request ISH-18895.
# Only the ID has to be correct: `update_usergroups_members_from_slack` looks the
# group up by ID and overwrites name/handle/description from Slack on each run.
USERGROUP_ID = "S0BL6GQPSQ3"
USERGROUP_NAME = "marketplace-foundations"
USERGROUP_HANDLE = "impact-marketplace-foundations"


def _get_models(apps):
    """Return (IncidentCategory, UserGroup) or None if Slack is not installed."""
    IncidentCategory = apps.get_model("incidents", "IncidentCategory")
    try:
        UserGroup = apps.get_model("slack", "UserGroup")
    except LookupError:
        logger.info("The 'slack' app is not installed, skipping.")
        return None
    return IncidentCategory, UserGroup


def link_foundations_usergroup(apps, _schema_editor):
    if not USERGROUP_ID:
        logger.warning(
            "USERGROUP_ID is not set (waiting on ISH-18895); skipping the link of "
            "'%s' to its Slack usergroup. The category keeps the usergroups copied "
            "by 0036, so incidents still page the superseded teams.",
            CATEGORY_NAME,
        )
        return

    models = _get_models(apps)
    if models is None:
        return
    IncidentCategory, UserGroup = models

    category = IncidentCategory.objects.filter(name=CATEGORY_NAME).first()
    if category is None:
        logger.warning(
            "Incident category '%s' not found, skipping usergroup link.",
            CATEGORY_NAME,
        )
        return

    if not hasattr(UserGroup, "incident_categories"):
        logger.warning("UserGroup has no 'incident_categories' field, skipping.")
        return

    with transaction.atomic():
        usergroup, created = UserGroup.objects.get_or_create(
            usergroup_id=USERGROUP_ID,
            defaults={"name": USERGROUP_NAME, "handle": USERGROUP_HANDLE},
        )
        if created:
            logger.info(
                "Created Slack usergroup '%s' (%s).", USERGROUP_NAME, USERGROUP_ID
            )
        usergroup.incident_categories.add(category)
        logger.info(
            "Linked usergroup '%s' to incident category '%s'.",
            USERGROUP_NAME,
            CATEGORY_NAME,
        )


def unlink_foundations_usergroup(apps, _schema_editor):
    """Unlink and delete only the usergroup this migration created.

    The usergroups copied by `0036` are untouched, so reversing this leaves
    `Foundations` paging the superseded teams exactly as it did before.
    """
    if not USERGROUP_ID:
        return

    models = _get_models(apps)
    if models is None:
        return
    _, UserGroup = models

    usergroup = UserGroup.objects.filter(usergroup_id=USERGROUP_ID).first()
    if usergroup is None:
        return

    with transaction.atomic():
        if hasattr(UserGroup, "incident_categories"):
            usergroup.incident_categories.clear()
        usergroup.delete()
        logger.info("Deleted Slack usergroup '%s'.", USERGROUP_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0036_add_foundations_incident_category"),
    ]

    operations = [
        migrations.RunPython(
            link_foundations_usergroup, unlink_foundations_usergroup
        ),
    ]
