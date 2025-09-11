from __future__ import annotations

from typing import TYPE_CHECKING, Any

import django_tables2 as tables
from django.conf import settings

from firefighter.firefighter.tables_utils import BASE_TABLE_ATTRS
from firefighter.incidents.models import Incident, IncidentCategory
from firefighter.incidents.models.incident import IncidentStatus

if TYPE_CHECKING:
    from datetime import timedelta


class IncidentTable(tables.Table):
    class Meta:
        model = Incident
        template_name = "incidents/table.html"
        fields = (
            "id",
            "title",
            "priority",
            "status",
            "environment",
            "incident_category",
            "incident_category__group",
            "created_at",
        )
        order_by = "-id"
        attrs: dict[str, str | dict[str, str]] = {
            **BASE_TABLE_ATTRS,
            "aria-label": "Incident list table",
        }

    id = tables.Column(
        linkify=True,
        attrs={"a": {"class": "text-primary hover:text-primary/80"}},
    )
    title = tables.Column(
        linkify=True,
        attrs={
            "a": {"class": "overflow-ellipsis"},
            "td": {"class": "px-3 py-4 max-w-sm md:max-w-md lg:max-w-lg truncate"},
            "th": {
                "class": "px-3 py-3 tracking-wider hover:underline uppercase text-xs font-medium text-left"
            },
        },
    )

    priority = tables.TemplateColumn(
        template_name="incidents/table/priority_column.html"
    )
    status = tables.TemplateColumn(
        template_name="incidents/table/status_column.html",
        attrs={"td": {"class": "px-3 py-4 whitespace-nowrap flex justify-around"}},
        extra_context={"IncidentStatus": IncidentStatus},
        order_by=("_status",),
    )
    created_at = tables.DateTimeColumn(
        short=True,
        format=settings.SHORT_DATETIME_FORMAT,
        attrs={"td": {"class": "table-td text-center"}},
    )
    environment = tables.Column(attrs={"td": {"class": "table-td text-center"}})
    incident_category = tables.Column(attrs={"td": {"class": "table-td text-center"}})
    incident_category__group = tables.Column(attrs={"td": {"class": "table-td text-center"}})


class IncidentCategoriesTable(tables.Table):
    class Meta:
        model = IncidentCategory
        template_name = "incidents/table.html"
        fields = (
            "name",
            "group__name",
            "mtbf",
            "incident_count",
        )
        attrs: dict[str, str | dict[str, str]] = {
            **BASE_TABLE_ATTRS,
            "aria-label": "Incident list table",
        }

    name = tables.Column(
        linkify=True,
        attrs={
            "td": {"class": "table-td text-left"},
            "a": {
                "class": "text-primary hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-200"
            },
        },
    )

    @staticmethod
    def render_mtbf(record: IncidentCategory, *args: Any) -> str:
        mtbf: timedelta | None = record.mtbf  # type: ignore[attr-defined]
        return str(mtbf).split(".", maxsplit=1)[0] if mtbf else "N/A"

    @staticmethod
    def render_incident_count(record: IncidentCategory, *args: Any) -> int:
        return int(record.incident_count) if record.incident_count else 0  # type: ignore[attr-defined]

    group__name = tables.Column(verbose_name="Group")
