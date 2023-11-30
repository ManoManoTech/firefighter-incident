from __future__ import annotations

from typing import Any

from django.contrib import admin

import firefighter.incidents.admin
from firefighter.pagerduty.models import (
    PagerDutyEscalationPolicy,
    PagerDutyIncident,
    PagerDutyOncall,
    PagerDutySchedule,
    PagerDutyService,
    PagerDutyTeam,
    PagerDutyUser,
)


@admin.register(PagerDutyUser)
class PagerDutyUserAdmin(admin.ModelAdmin[PagerDutyUser]):
    model = PagerDutyUser
    list_display = ["user", "pagerduty_id", "phone_number"]
    list_display_links = ["user", "pagerduty_id"]
    search_fields = ["id", "pagerduty_id", "user__name", "user__email"]
    autocomplete_fields = ["user"]


class PagerDutyAdminInline(admin.StackedInline[PagerDutyUser, Any]):
    model = PagerDutyUser


@admin.register(PagerDutyService)
class PagerDutyServiceAdmin(admin.ModelAdmin[PagerDutyService]):
    model = PagerDutyService

    ordering = ["name"]

    list_display = [
        "name",
        "summary",
        "status",
        "pagerduty_id",
        "created_at",
        "updated_at",
    ]

    list_display_links = ["summary", "name"]
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")

    list_max_show_all = 1000

    search_fields = ["summary", "pagerduty_id"]


@admin.register(PagerDutyIncident)
class PagerDutyIncidentAdmin(admin.ModelAdmin[PagerDutyIncident]):
    model = PagerDutyIncident

    list_display = [
        "summary",
        "service",
        "incident_key",
        "created_at",
        "updated_at",
    ]

    list_display_links = ["summary", "incident_key"]
    list_filter = ("service",)
    readonly_fields = ("created_at", "updated_at")

    list_max_show_all = 1000

    search_fields = ["summary", "incident_key", "title", "details"]


@admin.register(PagerDutyOncall)
class PagerDutyOncallAdmin(admin.ModelAdmin[PagerDutyOncall]):
    model = PagerDutyOncall

    list_display = [
        "user_name",
        "escalation_policy",
        "escalation_level",
        "schedule",
        "start",
        "end",
    ]
    readonly_fields = ("created_at", "updated_at")


@admin.register(PagerDutyEscalationPolicy)
class PagerDutyEscalationPolicyAdmin(admin.ModelAdmin[PagerDutyEscalationPolicy]):
    model = PagerDutyEscalationPolicy
    ordering = ["name"]
    list_display = [
        "name",
        "summary",
        "pagerduty_id",
    ]

    list_display_links = ["name", "summary"]

    list_max_show_all = 1000

    search_fields = ["name", "summary", "pagerduty_id"]


@admin.register(PagerDutySchedule)
class PagerDutyScheduleAdmin(admin.ModelAdmin[PagerDutySchedule]):
    model = PagerDutySchedule
    ordering = ["summary"]
    list_display = [
        "summary",
        "pagerduty_id",
    ]

    list_display_links = ["summary"]

    search_fields = ["summary", "pagerduty_id"]


@admin.register(PagerDutyTeam)
class PagerDutyTeamAdmin(admin.ModelAdmin[PagerDutyTeam]):
    model = PagerDutyTeam
    ordering = ["name"]
    list_display = [
        "name",
        "pagerduty_id",
    ]

    list_display_links = [
        "name",
    ]

    search_fields = ["name", "pagerduty_id"]


firefighter.incidents.admin.user_inlines.append(PagerDutyAdminInline)
