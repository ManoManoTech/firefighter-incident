from __future__ import annotations

import django_tables2 as tables

from firefighter.confluence.models import Runbook
from firefighter.firefighter.tables_utils import BASE_TABLE_ATTRS


class RunbookTable(tables.Table):
    class Meta:
        model = Runbook
        template_name = "incidents/table.html"
        fields = ("service_type",)
        attrs: dict[str, dict[str, str] | str] = {
            **BASE_TABLE_ATTRS,
            "aria-label": "Runbook list table",
        }

    # Disable for now as we link directly to Confluence
    name = tables.TemplateColumn(
        '<a href="{{record.page_url}}" class="text-primary hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-200">{{record.name}}</a>'
    )
