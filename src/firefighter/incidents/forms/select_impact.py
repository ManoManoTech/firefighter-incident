from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, cast

from django import forms

from firefighter.incidents.models.impact import (
    Impact,
    ImpactLevel,
    ImpactType,
    LevelChoices,
)

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import ManyRelatedManager

    from firefighter.incidents.models.impact import HasImpactProtocol


logger = logging.getLogger(__name__)


class SelectImpactForm(forms.Form):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "data" in kwargs:
            for key, value in kwargs["data"].items():
                if (
                    isinstance(key, str)
                    and key.startswith("set_impact_type_")
                    and isinstance(value, str)
                ):
                    impact_type_name = key[len("set_impact_type_") :]
                    with contextlib.suppress(ImpactLevel.DoesNotExist):
                        kwargs["data"][key] = ImpactLevel.objects.get(
                            value=value, impact_type__value=impact_type_name
                        )

        super().__init__(*args, **kwargs)

        for impact_type in ImpactType.objects.all().order_by("order"):
            field_name = f"set_impact_type_{impact_type.value}"
            self.fields[field_name] = forms.ModelChoiceField(
                label=impact_type.emoji + " " + impact_type.name,
                queryset=impact_type.levels.all().order_by("-order"),
                help_text=impact_type.help_text,
                initial=impact_type.levels.get(value=LevelChoices.NONE.value),
            )
            self.fields[field_name].label_from_instance = (  # type: ignore[attr-defined]
                lambda obj: obj.emoji + " " + obj.name
            )

    def suggest_priority_from_impact(self) -> int:
        """Suggest a priority from 1 (highest) to 5 (lowest) based on the impact choices."""
        if self.is_valid():
            impact: dict[str, ImpactLevel] = self.cleaned_data

            impact_values = [impact_type.value for impact_type in impact.values()]
            priorities = [level.priority for level in LevelChoices if level in impact_values]
            return min(priorities) if priorities else LevelChoices.NONE.priority
        return LevelChoices.NONE.priority

    @property
    def business_impact_new(self) -> str | None:
        """Get business impact. Will return N/A, Lowest, Low, Medium, High or Highest."""
        impact_value = ""
        if self.is_valid():
            impact: dict[str, ImpactLevel] = self.cleaned_data
            for impact_name in impact.values():
                if impact_name.impact_type.name == "Business Impact":
                    impact_value = impact_name.value

        return LevelChoices(impact_value).label if impact_value else None

    def save(self, incident: HasImpactProtocol) -> None:
        """Save the impact choices to the incident."""
        if self.is_valid():
            impacts: dict[str, ImpactLevel] = self.cleaned_data

            # Prepare a list of impact type slugs by removing the 'set_impact_type_' prefix
            impact_type_slugs: list[str] = [
                slug.replace("set_impact_type_", "") for slug in impacts
            ]

            # Fetch all relevant ImpactType instances in a single query
            impact_types: dict[str, ImpactType] = ImpactType.objects.in_bulk(
                impact_type_slugs, field_name="value"
            )

            impact_objects: list[Impact] = []

            for impact_type_slug, impact_level in impacts.items():
                impact_type_slug = impact_type_slug.replace(  # noqa: PLW2901
                    "set_impact_type_", ""
                )
                impact_type = impact_types.get(impact_type_slug)
                if impact_type is None:
                    logger.warning(
                        f"Could not find impact type {impact_type_slug} in incident {incident.id}"
                    )
                    continue

                impact = Impact(impact_type=impact_type, impact_level=impact_level)
                impact_objects.append(impact)

            # Create and save all Impact instances in one database call
            Impact.objects.bulk_create(impact_objects)
            impacts_related_manager: ManyRelatedManager[Impact] = cast(
                "ManyRelatedManager[Impact]",
                incident.impacts,
            )
            impacts_related_manager.add(*impact_objects)

        else:
            raise forms.ValidationError("Form is not valid")
