from __future__ import annotations

from django.contrib import admin

from firefighter.jira_app.admin import JiraIssueAdmin
from firefighter.raid.models import (
    JiraTicket,
    JiraTicketImpact,
    RaidArea,
)


class JiraTicketImpactInline(admin.TabularInline[JiraTicketImpact, JiraTicket]):
    model = JiraTicketImpact
    extra = 0
    raw_id_fields = ["impact"]


@admin.register(JiraTicket)
class JiraTicketAdmin(JiraIssueAdmin):
    model = JiraTicket
    list_display = ["id", "key", "summary", "incident"]
    list_display_links = ["id", "key", "summary"]
    search_fields = ["id", "key", "summary", "description"]
    list_select_related = ["incident"]

    autocomplete_fields = ["watchers", "assignee", "reporter", "incident"]
    inlines = [JiraTicketImpactInline]


@admin.register(RaidArea)
class RaidAreaAdmin(admin.ModelAdmin[RaidArea]):
    model = RaidArea
    list_display = ["id", "name", "area"]
    list_display_links = ["id", "name"]
    list_filter = ["area"]
    search_fields = ["id", "name"]
    ordering = ["area", "name"]
