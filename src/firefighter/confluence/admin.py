from __future__ import annotations

from django.contrib import admin

import firefighter.incidents.admin
from firefighter.confluence.models import ConfluencePage, PostMortem, Runbook
from firefighter.incidents.models.incident import Incident


@admin.register(ConfluencePage)
class ConfluencePageAdmin(admin.ModelAdmin[ConfluencePage]):
    model = ConfluencePage

    list_display: tuple[str, ...] = (
        "name",
        "page_id",
        "created_at",
        "updated_at",
    )
    search_fields: tuple[str, ...] = (
        "name",
        "page_id",
    )
    ordering: tuple[str, ...] = ("-created_at",)
    list_display_links = ["name", "page_id"]


class PostMortemAdminInline(admin.StackedInline[PostMortem, Incident]):
    model = PostMortem
    extra = 0
    verbose_name = "Confluence Post-Mortem"


@admin.register(PostMortem)
class PostMortemAdmin(ConfluencePageAdmin):
    model = PostMortem
    search_fields = ("name", "page_id", "incident__id")
    list_display = ("incident_id", "name", "page_id")
    ordering = ("-incident_id",)


@admin.register(Runbook)
class RunbookAdmin(ConfluencePageAdmin):
    model = Runbook
    list_display = ("service_type", "service_name", "title", "page_id")
    ordering = ("service_type", "service_name")
    list_display_links = ["service_type", "service_name", "title", "page_id"]
    list_filter = ("service_type",)


# Add inlines to incidents models
firefighter.incidents.admin.incident_inlines.append(PostMortemAdminInline)
