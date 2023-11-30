from __future__ import annotations

import logging
from itertools import groupby
from typing import TYPE_CHECKING, Any

from django import forms
from django.forms import ValidationError
from django_filters import Filter

from firefighter.incidents.views.date_filter import (
    get_date_range_from_special_date,
    get_range_look_args,
)

if TYPE_CHECKING:
    from datetime import date, datetime

    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)


class TextDateRangeField(forms.Field):
    def to_python(
        self, value: str | None
    ) -> tuple[date | None, date | None, str | None, str | None] | None:
        """Validate date range. Field is optional."""
        if not value or value.strip() == "":
            return None
        date_range = get_date_range_from_special_date(value)
        if date_range[0] is None and date_range[1] is None:
            err_msg = f"Invalid date range: {value}"
            raise ValidationError(err_msg)
        if (date_range[0] is not None and date_range[1] is not None) and date_range[
            0
        ] > date_range[1]:
            err_msg = f"Start date must be before end date ({date_range[0].strftime('%Y-%m-%d %H:%M:%S')} > {date_range[1].strftime('%Y-%m-%d %H:%M:%S')})."
            raise ValidationError(err_msg)

        return date_range


class FFDateRangeSingleFilter(Filter):
    """TODO Fix typings, implement tests, move in proper location."""

    field_class = TextDateRangeField

    def filter(self, qs: QuerySet[Any], value: Any) -> QuerySet[Any]:
        if not value:
            return qs

        qs = qs.filter(**self.get_lookup_kwarg(value))
        return qs.distinct() if self.distinct else qs

    def get_lookup_kwarg(
        self, value: tuple[datetime | None, datetime | None, Any, Any]
    ) -> dict[str, datetime]:
        field_name = self.field_name
        gte, lte, _, _ = value

        return get_range_look_args(gte, lte, field_name=field_name)


class FFDateRangeSingleFilterEmpty(FFDateRangeSingleFilter):
    def filter(self, qs: QuerySet[Any], value: Any) -> QuerySet[Any]:
        if not value:
            return qs

        return qs.distinct() if self.distinct else qs


class CustomCheckboxSelectMultiple(forms.widgets.CheckboxSelectMultiple):
    """Custom template."""

    template_name = "incidents/widgets/grouped_checkbox_nested.html"


class GroupedCheckboxSelectMultiple(CustomCheckboxSelectMultiple):
    """Widget to group checkboxes in a select multiple.
    TODO Make this generic!
    """

    def optgroups(
        self, name: str, value: list[Any], attrs: dict[str, Any] | None = None
    ) -> list[tuple[str | None, list[dict[str, Any]], int | None]]:
        """Return a list of optgroups for this widget."""
        self.choices = [
            (key, list(group))
            for key, group in groupby(self.choices, key=lambda x: x[0].instance.group)  # type: ignore[union-attr]
        ]
        return super().optgroups(name, value, attrs)
