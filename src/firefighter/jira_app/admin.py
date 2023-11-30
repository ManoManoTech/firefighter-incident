from __future__ import annotations

from django.contrib import admin

from firefighter.jira_app.models import JiraIssue, JiraUser


@admin.register(JiraUser)
class JiraUserAdmin(admin.ModelAdmin[JiraUser]):
    model = JiraUser
    list_display = ["id", "user"]
    list_display_links = ["id", "user"]
    search_fields = ["id", "user__username"]
    list_select_related = ["user"]


@admin.register(JiraIssue)
class JiraIssueAdmin(admin.ModelAdmin[JiraIssue]):
    model = JiraIssue
    list_display = ["id", "key", "summary"]
    list_display_links = ["id", "key", "summary"]
    search_fields = ["id", "key", "summary", "description"]

    autocomplete_fields = ["watchers", "assignee", "reporter"]
