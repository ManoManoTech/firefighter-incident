import logging
import uuid

from django.db import migrations, models
from django.db.models import Q
from firefighter.incidents.models.impact import LevelChoices

logger = logging.getLogger(__name__)


def remap_incidents(apps, schema_editor):
    ImpactLevel = apps.get_model("incidents", "ImpactLevel")
    Impact = apps.get_model("incidents", "Impact")

    to_delete_name = "Few employees with minor issues"
    impactlevel_to_delete = ImpactLevel.objects.filter(name=to_delete_name).first()
    name = "Significant issues for some employees"
    impactlevel = ImpactLevel.objects.filter(name=name).first()

    if impactlevel_to_delete is None:
        logger.warning(f"Failed to find ImpactLevel to delete {to_delete_name}.")
        return
    if impactlevel is None:
        logger.warning(f"Failed to find ImpactLevel {name}.")
        return
    impacts = Impact.objects.filter(impact_level=impactlevel_to_delete)

    for impact in impacts:
        try:
            impact.impact_level = impactlevel
            impact.save()
        except Exception:
            logger.warning(f"Failed to find ImpactLevel {name}.")


    try:
        impactlevel_to_delete.delete()
    except Exception:
        logger.warning(f"Failed to delete impact level {to_delete_name}.")


def update_impact_levels(apps, schema_editor):
    ImpactLevel = apps.get_model("incidents", "ImpactLevel")

    emoji_mapping = {
        "HT": "⏫",
        "HI": "🔼",
        "MD": "▶️",
        "LO": "🔽",
        "LT": "⏬",
    }

    updates = [
        {
            "old_name": "Critical issue for many customers",
            "new_name": None,
            "new_value": "HT",
            "new_order": 20,
        },
        {
            "old_name": "Some customers have issues",
            "new_name": "Some customers with major issues",
            "new_value": "HI",
            "new_order": 15,
        },
        {
            "old_name": "Few customers with minor issues",
            "new_name": "Some customers with significant issues",
            "new_value": "MD",
            "new_order": 10,
        },
        {
            "old_name": "No impact on customers",
            "new_name": None,
            "new_value": "LT",
            "new_order": 0,
        },
        {
            "old_name": "Key services inaccessible for most",
            "new_name": "Critical issues for many sellers",
            "new_value": "HT",
            "new_order": 20,
        },
        {
            "old_name": "Some sellers have significant issues",
            "new_name": "Some sellers with major issues",
            "new_value": "HI",
            "new_order": 15,
        },
        {
            "old_name": "Few sellers with minor issues",
            "new_name": "Some sellers with significant issues",
            "new_value": "MD",
            "new_order": 10,
        },
        {
            "old_name": "No impact on sellers",
            "new_name": None,
            "new_value": "LT",
            "new_order": 0,
        },
        {
            "old_name": "Significant issues for some employees",
            "new_name": "Major issues for internal users",
            "new_value": "LO",
            "new_order": 10,
        },
        {
            "old_name": "Critical internal tools down",
            "new_name": "Critical issues for internal users",
            "new_value": "MD",
            "new_order": 15,
        },
        {
            "old_name": "No impact on employees",
            "new_name": "Minor issues for internal users",
            "new_value": "LT",
            "new_order": 0,
        },
        {
            "old_name": "Whole business or revenue at risk",
            "new_name": "Critical business impact",
            "new_value": "HT",
            "new_order": 20,
        },
        {
            "old_name": "Significant business or revenue loss",
            "new_name": "Major business impact",
            "new_value": "HI",
            "new_order": 15,
        },
        {
            "old_name": "Minor impact on business or revenue",
            "new_name": "Significant business impact",
            "new_value": "MD",
            "new_order": 10,
        },
        {
            "old_name": "No impact on business or revenue",
            "new_name": None,
            "new_value": "LT",
            "new_order": 0,
        },
    ]
    adds = [
        {

            "name": "Some customers with minor issues",
            "value": LevelChoices.LOW.value,
            "order": 5,
            "impact_type_id": 3,
            "emoji": LevelChoices.LOW.emoji
        },
        {
            "name": "Some sellers with minor issues",
            "value": LevelChoices.LOW.value,
            "order": 5,
            "impact_type_id": 2,
            "emoji": LevelChoices.LOW.emoji
        },
        {
            "name": "Minor business impact",
            "value": LevelChoices.LOW.value,
            "order": 5,
            "impact_type_id": 1,
            "emoji": LevelChoices.LOW.emoji
        },
    ]

    for update in updates:
        try:
            impact_level = ImpactLevel.objects.filter(name=update["old_name"]).first()
            if impact_level:
                if update["new_name"] is not None:
                    impact_level.name = update["new_name"]
                impact_level.value = update["new_value"]
                impact_level.order = update["new_order"]
                impact_level.emoji = emoji_mapping.get(update["new_value"], impact_level.emoji)
                impact_level.save()
        except Exception:
            logger.warning(f"Failed to update ImpactLevel '{update["old_name"]}'.")

    for add in adds:
        try:
            new_impact_level = ImpactLevel(
                name=add["name"],
                value=add["value"],
                order=add["order"],
                emoji=add["emoji"],
                impact_type_id=add["impact_type_id"],
            )
            # new_impact_level.save()
        except Exception:
            logger.warning(f"Failed to create new ImpactLevel '{add["name"]}'.")


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0007_update_component_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="impactlevel",
            name="emoji",
            field=models.CharField(default="▶", max_length=5),
        ),
        migrations.RemoveConstraint(
          model_name="impactlevel",
          name="incidents_impactlevel_value_valid",
        ),
        migrations.AddConstraint(
          model_name="impactlevel",
          constraint=models.CheckConstraint(
            name="incidents_impactlevel_value_valid",
            check=Q(value__in=LevelChoices.values),
          ),
        ),
        migrations.AlterField(
            model_name='impactlevel',
            name='id',
            field=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False),
        ),
        migrations.RunPython(remap_incidents),
        migrations.RunPython(update_impact_levels),
    ]
