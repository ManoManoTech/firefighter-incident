from __future__ import annotations

from django.contrib import admin

from firefighter.jira_app.models import JiraIssue, JiraPostMortem, JiraUser


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


@admin.register(JiraPostMortem)
class JiraPostMortemAdmin(admin.ModelAdmin[JiraPostMortem]):
    model = JiraPostMortem
    list_display = ["jira_issue_key", "incident", "created_at", "created_by"]
    list_display_links = ["jira_issue_key", "incident"]
    search_fields = ["jira_issue_key", "jira_issue_id", "incident__id"]
    list_select_related = ["incident", "created_by"]
    autocomplete_fields = ["incident", "created_by"]
    readonly_fields = ["created_at", "updated_at", "issue_url"]

    def issue_url(self, obj: JiraPostMortem) -> str:
        return obj.issue_url
