from __future__ import annotations

import json
import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django import apps
from django.contrib import admin
from django.contrib.admin import AdminSite, helpers
from django.contrib.admin.decorators import action
from django.contrib.admin.utils import model_ngettext
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.messages import constants
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models import (
    Environment,
    Group,
    Incident,
    IncidentCategory,
    IncidentUpdate,
    Severity,
    User,
)
from firefighter.incidents.models.impact import (
    Impact,
    ImpactLevel,
    ImpactType,
    IncidentImpact,
)
from firefighter.incidents.models.incident_cost import IncidentCost
from firefighter.incidents.models.incident_cost_type import IncidentCostType
from firefighter.incidents.models.incident_membership import (
    IncidentMembership,
    IncidentRole,
)
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.incidents.models.metric_type import IncidentMetric, MetricType
from firefighter.incidents.models.milestone_type import MilestoneType
from firefighter.incidents.models.priority import Priority

if TYPE_CHECKING:
    from collections.abc import MutableSequence
    from decimal import Decimal

    from django.contrib.admin.options import (
        InlineModelAdmin,
        _ActionCallable,
        _FieldsetSpec,
    )
    from django.db.models.query import QuerySet
    from django.http.request import HttpRequest
    from django.utils.datastructures import _ListOrTuple

    from firefighter.slack.models.incident_channel import IncidentChannel

logger = logging.getLogger(__name__)

# Append inlines to these objects, from other modules
user_inlines: list[type[InlineModelAdmin[Any, User]]] = []
incident_category_inlines: list[type[InlineModelAdmin[Any, IncidentCategory]]] = []


class IncidentCostInline(admin.TabularInline[IncidentCost, Incident]):
    model = IncidentCost
    extra = 1
    fields = [
        "amount",
        "cost_type",
    ]


class IncidentImpactInline(admin.TabularInline[IncidentImpact, Incident]):
    model = IncidentImpact
    extra = 0
    raw_id_fields = ["impact"]


class IncidentMembershipInline(admin.StackedInline[IncidentMembership, Incident]):
    model = IncidentMembership
    extra: int = 0
    verbose_name = _("Incident Member")

    def has_change_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: Any | None = None,  # noqa: ARG002
    ) -> bool:
        return False


incident_inlines: MutableSequence[type[InlineModelAdmin[Any, Incident]]] = []


@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin[IncidentCategory]):
    model = IncidentCategory
    list_display = ["name", "group", "order", "private", "deploy_warning"]
    list_editable = ["order", "group", "private"]
    list_display_links = ["name"]
    list_filter = ["private", "deploy_warning", "group"]
    list_select_related = ["group"]
    ordering = ["group__order", "order"]
    search_fields = ["name", "group__name"]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    inlines = incident_category_inlines

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "group",
                    "order",
                    "private",
                    "deploy_warning",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


class IncidentCategoryInline(admin.StackedInline[IncidentCategory, IncidentCategory]):
    model = IncidentCategory
    fields = ["name", "order"]


class IncidentMetricInline(admin.TabularInline[IncidentMetric, Incident]):
    model = IncidentMetric
    extra = 0
    raw_id_fields = ["metric_type"]
    readonly_fields = ["duration", "metric_type", "incident"]
    can_delete = False

    @staticmethod
    def has_add_permission(*_: Any, **__: Any) -> bool:
        return False


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin[Environment]):
    model = Environment
    list_display = [
        "value",
        "name",
        "description",
        "order",
    ]
    list_editable = [
        "order",
    ]
    list_display_links = ["value"]

    def get_readonly_fields(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: Environment | None = None,
    ) -> _ListOrTuple[str]:
        """Deny changing the value of an existing object."""
        if obj:  # editing an existing object
            return *self.readonly_fields, "value"
        return self.readonly_fields


@admin.register(Severity)
class SeverityAdmin(admin.ModelAdmin[Severity]):
    model = Severity
    list_display = [
        "name",
        "emoji",
        "description",
        "order",
        "enabled_create",
        "enabled_update",
    ]
    list_editable = [
        "order",
    ]
    list_display_links = ["name"]


@admin.register(Priority)
class PriorityAdmin(admin.ModelAdmin[Priority]):
    model = Priority
    list_display = [
        "name",
        "emoji",
        "description",
        "sla",
        "order",
        "enabled_create",
        "enabled_update",
    ]
    list_editable = [
        "order",
    ]
    list_display_links = ["name"]


class IncidentUpdateInline(admin.StackedInline[IncidentUpdate, Incident]):
    model = IncidentUpdate
    show_change_link = True
    fields = [
        "event_ts",
        "event_type",
        "_status",
        "priority",
        "message",
        "incident_category",
        "created_by",
    ]
    extra = 0
    readonly_fields = [
        "priority",
        "message",
        "_status",
        "incident_category",
        "created_by",
        "commander",
        "communication_lead",
    ]

    def get_queryset(self, request: HttpRequest) -> QuerySet[IncidentUpdate]:
        # TODO Optimize DB queries from IncidentUpdate admin
        return (
            super()
            .get_queryset(request)
            .select_related(
                "priority",
                "incident_category",
                "incident",
                "incident__priority",
                "incident__incident_category",
                "incident_category__group",
                "created_by",
                "commander",
                "communication_lead",
            )
        )


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin[Incident]):
    model = Incident

    @action(description=_("Compute metrics from milestones"))
    def compute_metrics(
        self, request: HttpRequest, queryset: QuerySet[Incident]
    ) -> None:
        for incident in queryset:
            incident.compute_metrics()
        self.message_user(
            request,
            ngettext(
                "Computed metrics for %d incident.",
                "Computed metrics for %d incidents.",
                len(queryset),
            )
            % len(queryset),
            constants.SUCCESS,
        )

    @action(description=_("Compute and purge metrics from milestones"))
    def compute_and_purge_metrics(
        self, request: HttpRequest, queryset: QuerySet[Incident]
    ) -> None:
        """Will compute metrics for selected incidents and delete metrics that can no longer be computed."""
        for incident in queryset:
            incident.compute_metrics(purge=True)
        self.message_user(
            request,
            ngettext(
                "Computed/purged metrics for %d incident.",
                "Computed/purged metrics for %d incidents.",
                len(queryset),
            )
            % len(queryset),
            constants.SUCCESS,
        )

    @action(
        description=_("Send message on conversation"),
    )
    def send_message(
        self, request: HttpRequest, queryset: QuerySet[Incident]
    ) -> TemplateResponse | None:
        """Action to send a message in selected channels.
        This action first displays a confirmation page to enter the message.
        Next, it sends the message on all selected objects and redirects back to the change list (other fn).
        """
        opts = self.model._meta  # noqa: SLF001

        # Get all the targeted conversations
        target_conversations: list[IncidentChannel] = [
            inc.conversation for inc in queryset.all() if inc.conversation
        ]

        deletable_objects = target_conversations

        # The user has already entered the messages.
        # Send message(s) and return None to display the change list view again.
        if request.POST.get("post"):
            self.process_action_send_message(
                request=request, target_conversations=target_conversations
            )
            return None

        objects_name = model_ngettext(queryset)

        title = _("Type your message")

        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "objects_name": str(objects_name),
            "deletable_objects": [deletable_objects],
            "queryset": queryset,
            "opts": opts,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "media": self.media,
        }

        # Display the message edit page
        return TemplateResponse(
            request, "admin/send_message_conversation.html", context
        )

    def process_action_send_message(
        self, request: HttpRequest, target_conversations: list[IncidentChannel]
    ) -> None:
        # TODO Add and check permissions
        # if perms_needed:
        #     raise PermissionDenied

        message_text = request.POST.get("text")
        message_blocks_raw = request.POST.get("blocks")
        if message_text == "":
            message_text = None
        if not message_blocks_raw:
            message_blocks = None
        else:
            message_blocks = json.loads(message_blocks_raw)
            if isinstance(message_blocks, list) or all(
                isinstance(block, dict) for block in message_blocks
            ):
                raise ValueError("Blocks must be a list of JSON dicts")

        if message_blocks is None and message_text is None:
            raise ValueError("You need texts or blocks to send a message!")

        success = []
        errors = []

        for conversation in target_conversations:
            try:
                conversation.send_message(text=message_text, blocks=message_blocks)
                success.append(((conversation.name, conversation.incident_id), True))
            except SlackApiError as e:
                errors.append(((conversation.name, conversation.incident_id), False, e))

        if len(success) > 0:
            # XXX Test still working!
            self.message_user(
                request,
                ngettext(
                    _("Sent message on %d conversation (%s).")
                    % {", ".join(f"#{key[0][0]}, #{key[0][1]}" for key in success)},
                    f"Sent messages on %d conversations ({', '.join(f'#{key[0][0]}, #{key[0][1]}' for key in success)}).",
                    len(success),
                )
                % len(success),
                constants.SUCCESS,
            )
        if len(errors) > 0:
            self.message_user(
                request,
                format_html(
                    "Error sending message: <br/>{}",
                    "<br/>".join(
                        f"#{key[0][0]}, #{key[0][1]}: {key[2]}" for key in errors
                    ),
                ),
                constants.ERROR,
            )

        # Return None to display the change list page again.

    date_hierarchy = "created_at"
    autocomplete_fields = ["created_by", "incident_category"]
    actions: list[_ActionCallable[Any, Incident]] = [
        compute_metrics,
        compute_and_purge_metrics,
        send_message,
    ]
    list_display = [
        "id",
        "title",
        "short_description",
        "_status",
        "priority",
        "incident_category",
        "environment",
        "created_at",
        "updated_at",
    ]

    list_display_links = ["id", "title"]
    list_filter = ("_status", "priority", "incident_category", "environment")
    readonly_fields = (
        "created_at",
        "updated_at",
        "can_be_closed",
        "ask_for_milestones",
        "missing_milestones",
        "total_cost",
    )

    list_select_related = (
        "priority",
        "incident_category__group",
        "environment",
    )
    list_max_show_all = 1000

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "_status",
                    "ignore",
                    "private",
                    "created_at",
                    "updated_at",
                    "tags",
                )
            },
        ),
        (_("Relations"), {"fields": ("priority", "incident_category", "environment")}),
        (
            _("User Roles"),
            {
                "fields": ("created_by",),
            },
        ),
        (
            _("Properties"),
            {
                "classes": ("collapse",),
                "fields": (
                    "can_be_closed",
                    "ask_for_milestones",
                    "missing_milestones",
                    "severity",
                ),
            },
        ),
    )

    incident_inlines.append(IncidentUpdateInline)
    incident_inlines.append(IncidentMembershipInline)
    incident_inlines.append(IncidentCostInline)
    incident_inlines.append(IncidentImpactInline)
    incident_inlines.append(IncidentMetricInline)
    inlines = incident_inlines  # type: ignore[assignment]
    search_fields: list[str] = [
        "title",
        "description",
    ]  # We need to define it even if we redefine get_search_results so that the input is shown in the admin

    @staticmethod
    def total_cost(obj: Incident) -> int | float | Decimal:
        return obj.total_cost

    @staticmethod
    def get_search_results(
        request: HttpRequest,  # noqa: ARG004
        queryset: QuerySet[Incident],
        search_term: str,
    ) -> tuple[QuerySet[Incident], bool]:
        return Incident.objects.search(queryset=queryset, search_term=search_term)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Incident]:
        return (
            super()
            .get_queryset(request)
            .select_related(*self._get_select_related)
            .prefetch_related()
        )

    @cached_property
    def _get_select_related(self) -> list[str]:
        select_related = [
            "priority",
            "incident_category__group",
            "environment",
            "conversation",
            "incident_category",
            "created_by",
        ]
        if apps.apps.is_installed("firefighter.confluence"):
            select_related.append("postmortem_for")
        return select_related


@admin.register(IncidentUpdate)
class IncidentUpdateAdmin(admin.ModelAdmin[IncidentUpdate]):
    model = IncidentUpdate
    list_display = [
        "incident_id",
        "_status",
        "priority",
        "message",
        "incident_category",
        "created_by",
    ]
    list_display_links = ["_status"]
    list_filter = ("_status", "priority", "incident_category", "event_type")
    readonly_fields = ("created_at", "updated_at", "incident")
    list_select_related = ("priority", "incident_category", "incident", "created_by")
    search_fields = ["description", "message"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin[Group]):
    model = Group
    list_display = ["name", "order"]
    list_editable = [
        "order",
    ]
    ordering = ["order"]
    list_display_links = ["name"]
    inlines = [IncidentCategoryInline]
    search_fields = ["name"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    model = User
    list_max_show_all = 500
    inlines = user_inlines
    readonly_fields = [
        "commander_count",
        "communication_lead_count",
        "incidents_opened_count",
    ]
    list_display_links = ["email"]
    ordering = ["first_name", "last_name"]
    list_display = ("username", "email", "full_name", "is_staff", "is_active", "bot")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups", "bot")

    def __init__(self, model: type[User], admin_site: AdminSite) -> None:
        super().__init__(model, admin_site)
        self.fieldsets[2][1]["fields"] = ("bot", *self.fieldsets[2][1]["fields"])  # type: ignore
        self.fieldsets[1][1]["fields"] = (*self.fieldsets[1][1]["fields"], "avatar")  # type: ignore

    @staticmethod
    def commander_count(obj: User) -> int:
        return obj.roles_set.filter(role_type__slug="commander").count()

    @staticmethod
    def communication_lead_count(obj: User) -> int:
        return obj.roles_set.filter(role_type__slug="communication_lead").count()

    @staticmethod
    def incidents_opened_count(obj: User) -> int:
        return obj.incidents_created_by.count()

    def get_fieldsets(
        self,
        request: HttpRequest,
        obj: User | None = None,
    ) -> _FieldsetSpec:
        fieldsets = list(super().get_fieldsets(request, obj))
        fieldsets.append(
            (
                _("User statistics"),
                {
                    "fields": (
                        "commander_count",
                        "communication_lead_count",
                        "incidents_opened_count",
                    )
                },
            )
        )
        return fieldsets


@admin.register(IncidentMembership)
class IncidentMembershipAdmin(admin.ModelAdmin[IncidentMembership]):
    model = IncidentMembership
    fields = ("user", "incident")
    list_display = ("user", "incident")


class ImpactLevelInline(admin.TabularInline[ImpactLevel, Incident]):
    model = ImpactLevel
    extra = 0


@admin.register(IncidentCost)
class IncidentCostAdmin(admin.ModelAdmin[IncidentCost]):
    model = IncidentCost
    fields = ("incident", "amount", "cost_type", "details")
    list_display = ("incident", "amount", "cost_type")
    search_fields = ["incident__id", "incident__title", "amount", "cost_type"]
    autocomplete_fields = ["incident"]


@admin.register(IncidentCostType)
class IncidentCostTypeAdmin(admin.ModelAdmin[IncidentCostType]):
    model = IncidentCostType
    list_display = ("name", "description")


@admin.register(Impact)
class ImpactAdmin(admin.ModelAdmin[Impact]):
    model = Impact


@admin.register(ImpactType)
class ImpactTypeAdmin(admin.ModelAdmin[ImpactType]):
    model = ImpactType
    prepopulated_fields = {"value": ["name"]}

    list_display = ("name", "value", "help_text")
    search_fields = ["name", "value", "help_text"]

    inlines = [ImpactLevelInline]


@admin.register(ImpactLevel)
class ImpactLevelAdmin(admin.ModelAdmin[ImpactLevel]):
    model = ImpactLevel
    list_display = (
        "value",
        "name",
        "impact_type",
    )
    search_fields = [
        "name",
        "impact_type",
    ]
    list_filter = ("impact_type", "value")


@admin.register(MilestoneType)
class MilestoneTypeAdmin(admin.ModelAdmin[MilestoneType]):
    model = MilestoneType
    list_display = (
        "name",
        "user_editable",
        "required",
        "asked_for",
    )

    search_fields = ["name", "description", "summary"]
    prepopulated_fields = {"event_type": ["name"], "summary": ["name"]}


@admin.register(MetricType)
class MetricTypeAdmin(admin.ModelAdmin[MetricType]):
    model = MetricType
    list_display = (
        "name",
        "code",
        "milestone_lhs",
        "milestone_rhs",
    )

    search_fields = ["name", "code"]
    prepopulated_fields = {"type": ["name"]}


@admin.register(IncidentMetric)
class IncidentMetricAdmin(admin.ModelAdmin[IncidentMetric]):
    model = IncidentMetric
    list_display = (
        "metric_type",
        "duration",
        "incident",
    )
    search_fields = ["incident__title", "metric_type__title", "value"]
    list_filter = ("metric_type",)


@admin.register(IncidentRoleType)
class IncidentRoleTypeAdmin(admin.ModelAdmin[IncidentRoleType]):
    """IncidentRoleTypes are fixed at the moment (only commander and communication lead)."""

    list_display = ["name", "emoji", "required", "order"]
    readonly_fields = ["id"]
    ordering = ["order"]
    fieldsets = [
        (
            _("⚙️ General Information"),
            {"fields": ["id", "slug", "name", "emoji", "required", "order"]},
        ),
        (
            _("📝 Short Descriptions"),
            {"fields": ["summary", "summary_first_person", "description", "aka"]},
        ),
    ]
    search_fields = ["name", "slug", "emoji", "summary", "description"]
    list_filter = ["required"]
    prepopulated_fields = {"slug": ["name"]}

    @staticmethod
    def has_delete_permission(
        _request: HttpRequest, _obj: IncidentRoleType | None = None
    ) -> bool:
        return False


@admin.register(IncidentRole)
class IncidentRoleAdmin(admin.ModelAdmin[IncidentRole]):
    model = IncidentRole
    list_display = (
        "incident",
        "user",
        "role_type",
    )
    search_fields = ["incident__title", "user__email", "role_type__name"]
    list_filter = ("role_type",)
    autocomplete_fields = ["incident", "user", "role_type"]
    readonly_fields = ["incident", "user", "role_type"]
