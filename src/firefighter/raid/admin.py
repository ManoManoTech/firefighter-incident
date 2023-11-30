from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from firefighter.jira_app.admin import JiraIssueAdmin
from firefighter.raid.models import (
    JiraTicket,
    JiraTicketImpact,
    Qualifier,
    QualifierRotation,
    RaidArea,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django.forms.models import ModelForm
    from django.http import HttpRequest


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


@admin.register(QualifierRotation)
class QualifierRotationAdmin(admin.ModelAdmin[QualifierRotation]):
    model = QualifierRotation
    list_display = ["day", "jira_user", "protected"]
    list_select_related = ["jira_user", "jira_user__user"]
    list_display_links = ["day"]

    ordering = ["-day"]
    search_fields = ["day", "jira_user__user__username"]
    date_hierarchy = "day"

    autocomplete_fields = ["jira_user"]

    def has_add_permission(
        self, _request: HttpRequest, _obj: QualifierRotation | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, _request: HttpRequest, _obj: QualifierRotation | None = None
    ) -> bool:
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: QualifierRotation,
        form: ModelForm[QualifierRotation],
        change: bool,  # noqa: FBT001
    ) -> None:
        obj.protected = True
        super().save_model(request, obj, form, change)

    @admin.action(description="Unprotect rotation date", permissions=["change"])
    def make_unprotected(
        self, _request: HttpRequest, queryset: QuerySet[QualifierRotation]
    ) -> None:
        queryset.update(protected=False)

    actions = [make_unprotected]

    fieldsets = (
        (
            _("Rotation"),
            {
                "fields": (
                    "day",
                    "jira_user",
                )
            },
        ),
        (
            _("Protected"),
            {
                "fields": ("protected",),
            },
        ),
    )


@admin.register(Qualifier)
class QualifiersListAdmin(admin.ModelAdmin[Qualifier]):
    model = Qualifier
    list_display = ["jira_user"]
    list_select_related = ["jira_user", "jira_user__user"]

    ordering = ["id"]
    search_fields = ["jira_user__user__username"]

    autocomplete_fields = ["jira_user"]

    def has_change_permission(
        self, _request: HttpRequest, _obj: Qualifier | None = None
    ) -> bool:
        return False


@admin.register(RaidArea)
class RaidAreaAdmin(admin.ModelAdmin[RaidArea]):
    model = RaidArea
    list_display = ["id", "name", "area"]
    list_display_links = ["id", "name"]
    list_filter = ["area"]
    search_fields = ["id", "name"]
    ordering = ["area", "name"]
