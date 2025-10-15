from __future__ import annotations

import logging
import re
from copy import deepcopy
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import django_filters
from django.apps import apps
from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models, transaction
from django.urls import reverse
from django.utils.text import Truncator
from django.utils.timezone import localtime
from django_filters.filters import (
    ModelMultipleChoiceFilter,
    MultipleChoiceFilter,
    OrderingFilter,
)
from django_stubs_ext.db.models import TypedModelMeta
from taggit.managers import TaggableManager

from firefighter.firefighter.fields_forms_widgets import (
    CustomCheckboxSelectMultiple,
    FFDateRangeSingleFilter,
    GroupedCheckboxSelectMultiple,
)
from firefighter.incidents import signals
from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.group import Group
from firefighter.incidents.models.incident_category import IncidentCategory
from firefighter.incidents.models.incident_membership import (
    IncidentMembership,
    IncidentRole,
)
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.metric_type import IncidentMetric, MetricType
from firefighter.incidents.models.milestone_type import MilestoneType
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.models.severity import Severity
from firefighter.incidents.models.user import User
from firefighter.incidents.signals import (
    incident_closed,
    incident_created,
    incident_updated,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence  # noqa: F401
    from decimal import Decimal
    from uuid import UUID

    from django.db.models.query import QuerySet
    from django_stubs_ext.db.models.manager import RelatedManager

    from firefighter.incidents.models.impact import (
        Impact,  # noqa: F401
        IncidentImpact,  # noqa: F401
    )
    from firefighter.incidents.models.incident_cost import IncidentCost
    from firefighter.slack.models import IncidentChannel

    if settings.ENABLE_CONFLUENCE:
        from firefighter.confluence.models import PostMortem


NON_ALPHANUMERIC_CHARACTERS = re.compile(r"[^\da-zA-Z]+")

TD0 = timedelta(0)


class IncidentManager(models.Manager["Incident"]):
    def get_or_none(self, **kwargs: Any) -> Incident | None:
        try:
            return self.get(**kwargs)
        except Incident.DoesNotExist:
            return None

    def declare(self, **kwargs: Any) -> Incident:
        """Create an Incident and its first IncidentUpdate.
        Send the incident_created signal.
        Returns the saved incident, no need to .save().
        """
        with transaction.atomic():
            if "private" not in kwargs:
                kwargs["private"] = kwargs["incident_category"].private
            if "severity" not in kwargs and "priority" in kwargs:
                kwargs["severity"] = Severity.objects.get(
                    value=kwargs["priority"].value
                )
            incident: Incident = super().create(**kwargs)
            for required_default_role in IncidentRoleType.objects.filter(required=True):
                incident.roles_set.add(
                    IncidentRole.objects.create(
                        incident=incident,
                        role_type=required_default_role,
                        user=incident.created_by,
                    )
                )

            first_incident_update = IncidentUpdate(
                title=incident.title,
                description=incident.description,
                status=incident.status,  # type: ignore[misc]
                priority=incident.priority,
                incident_category=incident.incident_category,
                created_by=incident.created_by,
                commander=incident.created_by,
                incident=incident,
                event_ts=incident.created_at,
            )

            milestone_declared = IncidentUpdate(
                created_by=incident.created_by,
                incident=incident,
                event_type="declared",
                event_ts=incident.created_at,
            )
            first_incident_update.save()
            milestone_declared.save()

            incident.members.add(incident.created_by)

        # Either we have an incident or an error was thrown
        incident_created.send_robust(sender=__name__, incident=incident)
        return incident

    @staticmethod
    def search(
        queryset: QuerySet[Incident] | None, search_term: str
    ) -> tuple[QuerySet[Incident], bool]:
        """Search for incidents using a search term, on the title and description fields.

        Args:
            queryset (QuerySet[Incident] | None): Queryset to search in. If None, search in all incidents. The Queryset allows to search on a subset of incidents (already filtered).
            search_term (str): Search term.

        Returns:
            tuple[QuerySet[Incident], bool]: Queryset of incidents matching the search term, and a boolean indicating if the search may contain duplicates objects.
        """
        if queryset is None:
            queryset = Incident.objects.all()

        # If not search, return the original queryset
        if search_term is None or search_term.strip() == "":
            return queryset, False

        queryset_search_id = None

        # If the search is just an int, search for this ID + regular search
        try:
            search_term_as_int = int(search_term)
        except ValueError:
            pass
        else:
            queryset_search_id = deepcopy(queryset)
            queryset_search_id = queryset_search_id.filter(id=search_term_as_int)

        # Postgres search on title + description
        # XXX Improve search performance and relevance
        vector = SearchVector("title", config="english", weight="A") + SearchVector(
            "description", config="english", weight="B"
        )
        query = SearchQuery(search_term, config="english", search_type="websearch")
        queryset = (
            queryset.annotate(rank=SearchRank(vector, query))
            .filter(rank__gte=0.1)
            .order_by("-rank")
        )

        # Add the search by id to the search by text if needed
        if queryset_search_id:
            queryset |= queryset_search_id  # type: ignore[operator]

        return queryset, False


class Incident(models.Model):
    # pylint: disable=no-member
    objects: IncidentManager = IncidentManager()

    id = models.BigAutoField[int, int](primary_key=True, auto_created=True)
    title = models.CharField[str, str](max_length=128)
    description = models.TextField[str, str]()
    _status = models.IntegerField(
        db_column="status",
        choices=IncidentStatus.choices,
        default=IncidentStatus.OPEN,
        verbose_name="Status",
    )
    severity = models.ForeignKey(
        Severity,
        on_delete=models.PROTECT,
        help_text="Severity (legacy, superseded by priority)",
        null=True,
        blank=True,
    )
    severity.system_check_deprecated_details = {
        "msg": "The Incident.severity field has been deprecated.",
        "hint": "Use Incident.priority instead.",
        "id": "fields.W921",
    }
    priority = models.ForeignKey(
        Priority,
        on_delete=models.PROTECT,
        help_text="Priority",
    )
    incident_category = models.ForeignKey(
        IncidentCategory, on_delete=models.PROTECT
    )
    environment = models.ForeignKey(
        Environment, on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="incidents_created_by",
        blank=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(
        null=True, blank=True
    )  # XXX-ZOR make this an event
    closure_reason = models.CharField(
        max_length=50,
        choices=ClosureReason.choices,
        null=True,
        blank=True,
        help_text="Reason for direct incident closure bypassing normal workflow",
    )
    closure_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference incident ID or external link for closure context",
    )

    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for incident (zendesk_ticket_id, seller_contract_id, etc.)",
    )

    # XXX-ZOR pick a more meaningful name. maybe 'hidden'
    # XXX-ZOR document intent and impl. status
    ignore = models.BooleanField(
        default=False,
        help_text="An ignored incident can be closed right away. In the future, it won't affect statistics or appear in reports. This is useful for duplicates incidents, or false-positives.",
    )
    private = models.BooleanField(
        default=False,
        help_text="A private incident is not communicated in #tech-incidents, and its created conversation is private. In the future, we may restrict the visibility to incident members only.",
    )
    tags = TaggableManager(blank=True)

    members = models.ManyToManyField["User", "IncidentMembership"](
        User,
        through=IncidentMembership,
        through_fields=("incident", "user"),
    )
    impacts = models.ManyToManyField["Impact", "IncidentImpact"](
        "Impact", through="IncidentImpact"
    )

    metrics = models.ManyToManyField["MetricType", "IncidentMetric"](
        MetricType,
        through="IncidentMetric",
    )
    roles = models.ManyToManyField[User, "IncidentRole"](
        User, through=IncidentRole, related_name="incident_roles_set"
    )

    if TYPE_CHECKING:
        roles_set: RelatedManager[IncidentRole]

    class Meta(TypedModelMeta):
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s__status_valid",
                check=models.Q(_status__in=IncidentStatus.values),
            ),
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_closure_reason_valid",
                check=models.Q(closure_reason__in=[*ClosureReason.values, None]),
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.id} - {self.title}"

    def get_absolute_url(self) -> str:
        return reverse("incidents:incident-detail", kwargs={"incident_id": self.id})

    @property
    def short_description(self) -> str:
        return Truncator(self.description).chars(100)

    @property
    def slack_channel_name(self) -> str | None:
        if hasattr(self, "conversation"):
            return self.conversation.name
        return None

    @property
    def canonical_name(self) -> str:
        if self.created_at is None:
            raise RuntimeError(
                "Incident must be saved before canonical_name can be computed"
            )
        return f"{localtime(self.created_at).strftime('%Y%m%d')}-{str(self.id)[:8]}"

    @property
    def status(self) -> IncidentStatus:
        return IncidentStatus(self._status)

    @status.setter
    def status(self, status: IncidentStatus) -> None:
        self._status = status

    @property
    def slack_channel_url(self) -> str | None:
        if hasattr(self, "conversation"):
            return self.conversation.link
        return None

    @property
    def status_page_url(self) -> str:
        """Similar with `get_absolute_url` but with full domain, to be used out of the website."""
        return f"{settings.BASE_URL}{self.get_absolute_url()}"

    @property
    def needs_postmortem(self) -> bool:
        return (
            bool(
                self.priority
                and self.environment
                and self.priority.needs_postmortem
                and self.environment.value == "PRD"
            )
            if apps.is_installed("firefighter.confluence")
            else False
        )

    @property
    def can_be_closed(self) -> tuple[bool, list[tuple[str, str]]]:
        # XXX-ZOR we should use a proper FSM abstraction
        cant_closed_reasons: list[tuple[str, str]] = []

        # Allow direct closure when closure_reason is provided (bypasses normal workflow)
        if self.closure_reason:
            return True, []

        if self.ignore:
            return True, []
        if self.needs_postmortem:
            if self.status.value != IncidentStatus.POST_MORTEM:
                cant_closed_reasons.append(
                    (
                        "STATUS_NOT_POST_MORTEM",
                        f"Incident is not in PostMortem status, and needs one because of its priority and environment ({self.priority.name}/{self.environment.value}).",
                    )
                )
        elif self.status.value < IncidentStatus.MITIGATED:
            cant_closed_reasons.append(
                (
                    "STATUS_NOT_MITIGATED",
                    f"Incident is not in {IncidentStatus.MITIGATED.label} status (currently {self.status.label}).",
                )
            )
        missing_milestones = self.missing_milestones()
        if len(missing_milestones) > 0:
            cant_closed_reasons.append(
                (
                    "MISSING_REQUIRED_KEY_EVENTS",
                    f"Missing key events: {', '.join(missing_milestones)}",
                )
            )

        if len(cant_closed_reasons) > 0:
            return False, cant_closed_reasons
        return True, cant_closed_reasons

    @property
    def ask_for_milestones(self) -> bool:
        # XXX-ZOR we should use a proper FSM abstraction
        return len(self.missing_milestones()) > 0

    def missing_milestones(self) -> list[str]:
        """Returns all required Milestones still needed to compute the metrics."""
        if self.ignore:
            return []

        # We get a list of all event_type of IncidentUpdates...
        milestones_list = (
            IncidentUpdate.objects.filter(
                incident_id=self.id,
                event_ts__isnull=False,
                event_type__isnull=False,
            )
            .aggregate(milestone_list=ArrayAgg("event_type", distinct=True, default=[]))
            .get("milestone_list", [])
        )

        incident_milestones: set[str] = set(cast('list["str"]', milestones_list))
        required_milestone_types = set(
            MilestoneType.objects.filter(required=True).values_list(
                "event_type", flat=True
            )
        )
        # And we make the differences of the sets
        return list(required_milestone_types - incident_milestones)

    @property
    def latest_updates_by_type(self) -> dict[str, IncidentUpdate]:
        qs = (
            self.incidentupdate_set.order_by("event_type", "-event_ts")
            .distinct("event_type")
            .filter(event_type__isnull=False)
        )
        return {iu.event_type: iu for iu in qs}  # type: ignore

    @property
    def total_cost(self) -> int | float | Decimal:
        qs: QuerySet[IncidentCost] = self.incident_cost_set.exclude(amount__isnull=True)
        return sum(iu.amount for iu in qs if iu.amount is not None)

    def compute_metrics(self, *, purge: bool = False) -> None:
        """Compute all metrics (time to fix, ...) from events."""
        latest_updates_by_type = self.latest_updates_by_type

        for metric_type in MetricType.objects.all():
            lhs_type = metric_type.milestone_lhs.event_type
            rhs_type = metric_type.milestone_rhs.event_type

            lhs = latest_updates_by_type.get(lhs_type, None)
            rhs = latest_updates_by_type.get(rhs_type, None)

            if not lhs or not lhs.event_ts:
                logger.info(
                    f"Missing operand '{lhs_type}' on metric {metric_type.type} for #{self.id}"
                )
                if purge:
                    IncidentMetric.objects.filter(
                        incident=self, metric_type=metric_type
                    ).delete()
                continue
            if not rhs or not rhs.event_ts:
                logger.info(
                    f"Missing operand '{rhs_type}' on metric {metric_type.type} for #{self.id}"
                )
                if purge:
                    IncidentMetric.objects.filter(
                        incident=self, metric_type=metric_type
                    ).delete()
                continue
            duration = lhs.event_ts - rhs.event_ts
            if duration < TD0:
                logger.warning(
                    f"Tried to compute a negative metric! Metric {metric_type.type} for #{self.id} has a duration of {duration} ({lhs.event_type}:{lhs.event_ts} - {rhs.event_type}:{rhs.event_ts})"
                )
                if purge:
                    IncidentMetric.objects.filter(
                        incident=self, metric_type=metric_type
                    ).delete()
                continue
            IncidentMetric.objects.update_or_create(
                incident=self,
                metric_type=metric_type,
                defaults={"duration": duration},
            )
        self.save()

    def build_invite_list(self) -> list[User]:
        """Send a Django Signal to get the list of users to invite from different integrations (Slack, Confluence, PagerDuty...).

        Returns:
            list[User]: Potentially non-unique list of Users to invite
        """
        users_list: list[User] = []

        # Send signal to modules (Confluence, PagerDuty...)
        result_users: list[tuple[Any, Exception | Iterable[User]]] = (
            signals.get_invites.send_robust(sender=None, incident=self)
        )

        # Aggregate the results
        for provider in result_users:
            if isinstance(provider[1], BaseException):
                logger.warning(
                    f"Provider {provider[0]} returned an error getting Users to invite: {provider[1]}."
                )
                continue

            users_list.extend(provider[1])

        logger.debug(f"Get invites users list: {users_list}")

        return users_list

    def update_roles(
        self,
        updater: User,
        roles_mapping: dict[str, User | None] | dict[str, User],
    ) -> IncidentUpdate:
        """Update the roles related to an incident, and create an IncidentUpdate.
        For each role, provide a User or None.

        This function will update the incident, create an [IncidentUpdate][firefighter.incidents.models.incident_update.IncidentUpdate], and trigger the [incident_updated][firefighter.incidents.signals.incident_updated] signal, with `update_roles` sender.

        Args:
            updater (User): The user who is updating the roles.
            roles_mapping (dict[str, User | None], optional): A dict of roles to update, with the new User or None. Defaults to None.

        Returns:
            IncidentUpdate: The created IncidentUpdate with the updated roles.
        """
        updated_fields: list[str] = []

        # Handle roles
        for role_slug, assigned_user in roles_mapping.items():
            try:
                role_type = IncidentRoleType.objects.get(slug=role_slug)
            except IncidentRoleType.DoesNotExist:
                logger.warning(f"Unknown role type: {role_slug}")
                continue
            if assigned_user is not None:
                IncidentRole.objects.update_or_create(
                    incident=self,
                    role_type=role_type,
                    defaults={"user": assigned_user},
                )
                logger.debug(
                    f"Updated role {role_slug} to user ID={assigned_user.id} for #{self.id}"
                )
                updated_fields.append(f"{role_slug}_id")
            elif role_type.required:
                logger.warning(f"Cannot remove required role: {role_slug}")
            else:
                IncidentRole.objects.filter(incident=self, role_type=role_type).delete()
                updated_fields.append(f"{role_slug}_id")

        # Handle legacy roles with IncidentUpdate
        # XXX(dugab): Custom roles are not saved in IncidentUpdate at the moment

        incident_update = IncidentUpdate(
            incident=self,
            created_by=updater,
            commander=roles_mapping.get("commander"),
            communication_lead=roles_mapping.get("communication_lead"),
        )
        incident_update.save()

        incident_updated.send_robust(
            "update_roles",
            incident=self,
            incident_update=incident_update,
            updated_fields=updated_fields,
        )

        return incident_update

    def create_incident_update(
        self: Incident,
        message: str | None = None,
        status: int | None = None,
        priority_id: UUID | None = None,
        incident_category_id: UUID | None = None,
        created_by: User | None = None,
        event_type: str | None = None,
        title: str | None = None,
        description: str | None = None,
        environment_id: str | None = None,
        event_ts: datetime | None = None,
    ) -> IncidentUpdate:
        updated_fields: list[str] = []

        def _update_incident_field(
            incident: Incident, field_name: str, value: Any, updated_fields: list[str]
        ) -> None:
            if value is not None:
                setattr(incident, field_name, value)
                updated_fields.append(field_name)

        _update_incident_field(self, "_status", status, updated_fields)
        _update_incident_field(self, "priority_id", priority_id, updated_fields)
        _update_incident_field(self, "incident_category_id", incident_category_id, updated_fields)
        _update_incident_field(self, "title", title, updated_fields)
        _update_incident_field(self, "description", description, updated_fields)
        _update_incident_field(self, "environment_id", environment_id, updated_fields)

        old_priority = self.priority if priority_id is not None else None

        if updated_fields:
            self.save(update_fields=[*updated_fields, "updated_at"])

        if not (updated_fields or message):
            raise ValueError("No updated fields or message provided.")
        with transaction.atomic():
            incident_update = IncidentUpdate(
                incident=self,
                status=status,  # type: ignore
                priority_id=priority_id,
                environment_id=environment_id,
                incident_category_id=incident_category_id,
                message=message,
                created_by=created_by,
                title=title,
                description=description,
                event_type=event_type,
                event_ts=event_ts,
            )
            incident_update.save()

            if status == IncidentStatus.MITIGATED:
                IncidentUpdate.objects.update_or_create(
                    incident_id=self.id,
                    event_type="recovered",
                    defaults={
                        "event_ts": incident_update.event_ts,
                        "created_by": incident_update.created_by,
                    },
                )
                self.compute_metrics()

        incident_updated.send_robust(
            "update_status",
            incident=self,
            incident_update=incident_update,
            updated_fields=updated_fields,
            old_priority=old_priority,
        )

        if self.status == IncidentStatus.CLOSED:
            logger.debug("Close incident: sending signal")
            incident_closed.send_robust(sender=__name__, incident=self)

        return incident_update

    if TYPE_CHECKING:
        if settings.ENABLE_CONFLUENCE:
            postmortem_for: PostMortem
            postmortem_for_id: UUID
        priority_id: UUID
        environment_id: UUID
        component_id: UUID
        conversation: IncidentChannel
        incidentupdate_set: QuerySet[IncidentUpdate]


def incident_category_filter_choices_queryset(_: Any) -> QuerySet[IncidentCategory]:
    """Queryset for choices of IncidentCategories in IncidentFilterSet.
    Moved it as a function because models are not loaded when creating filters.
    """
    return (
        IncidentCategory.objects.all()
        .select_related("group")
        .order_by(
            "group__order",
            "name",
        )
    )


class IncidentFilterSet(django_filters.FilterSet):
    """Set of filters for incidents, shared by Web UI and API."""

    id = django_filters.CharFilter(lookup_expr="iexact")

    status = MultipleChoiceFilter(
        choices=IncidentStatus.choices,
        label="Status",
        field_name="_status",
        widget=CustomCheckboxSelectMultiple,
        null_value="All Statuses",
    )
    environment = ModelMultipleChoiceFilter(
        queryset=Environment.objects.all(),
        widget=CustomCheckboxSelectMultiple,
    )
    priority = ModelMultipleChoiceFilter(
        queryset=Priority.objects.all(),
        widget=CustomCheckboxSelectMultiple,
    )
    group = ModelMultipleChoiceFilter(
        queryset=Group.objects.all(), field_name="incident_category__group_id", label="Group"
    )
    incident_category = ModelMultipleChoiceFilter(
        queryset=incident_category_filter_choices_queryset,
        label="Incident category",
        widget=GroupedCheckboxSelectMultiple,
    )
    created_at = FFDateRangeSingleFilter(field_name="created_at")
    order_by = OrderingFilter(
        fields=["priority", "title", "id", "created_at", "created_by"]
    )

    # User filters are not shown in the UI, but are available in the API or query params for the Web UI
    created_by = ModelMultipleChoiceFilter(queryset=User.objects.all())

    search = django_filters.CharFilter(
        field_name="search", method="incident_search", label="Search"
    )

    @staticmethod
    def incident_search(
        queryset: QuerySet[Incident], _name: str, value: str
    ) -> QuerySet[Incident]:
        """Search incidents by title, description, and ID.

        Args:
            queryset (QuerySet[Incident]): Queryset to search in.
            _name:
            value (str): Value to search for.

        Returns:
            QuerySet[Incident]: Search results.
        """
        return Incident.objects.search(queryset=queryset, search_term=value)[0]

    class Meta(TypedModelMeta):
        model = Incident
        fields = {
            "created_at": ["gte", "lte", "lt", "gt", "exact"],
            "id": ["gte", "lte", "lt", "gt", "iexact", "in"],
            "_status": ["gte", "lte", "lt", "gt"],
            "environment__value": ["exact", "in"],
            "ignore": ["exact"],
        }
