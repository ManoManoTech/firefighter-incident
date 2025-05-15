from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import django_filters
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models
from django.db.models import (
    Count,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.fields import DurationField
from django.db.models.functions import Cast
from django.urls import reverse
from django.utils import timezone
from django_filters.filters import ModelMultipleChoiceFilter
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.firefighter.fields_forms_widgets import (
    CustomCheckboxSelectMultiple,
    FFDateRangeSingleFilterEmpty,
)
from firefighter.incidents.models.group import Group
from firefighter.incidents.models.metric_type import IncidentMetric

if TYPE_CHECKING:
    from django.conf import settings


logger = logging.getLogger(__name__)
TZ = timezone.get_current_timezone()


class ComponentManager(models.Manager["Component"]):
    model: type[Component]

    def queryset_with_mtbf(
        self,
        date_from: datetime,
        date_to: datetime,
        queryset: QuerySet[Component] | None = None,
        metric_type: str = "time_to_fix",
        field_name: str = "mtbf",
    ) -> QuerySet[Component]:
        """Returns a queryset of components with an additional `mtbf` field."""
        date_to = min(date_to, datetime.now(tz=TZ))

        date_interval = date_to - date_from
        queryset = queryset or self.get_queryset()

        return (
            queryset.order_by("group__order", "order")
            .annotate(
                metric_subquery=Subquery(
                    IncidentMetric.objects.filter(
                        incident__component=OuterRef("pk"),
                        metric_type__type=metric_type,
                        incident__created_at__gte=date_from,
                        incident__created_at__lte=date_to,
                    )
                    .values("incident__component")
                    .annotate(sum_downtime=Sum("duration"))
                    .values("sum_downtime")
                )
            )
            .annotate(
                incident_count=Count(
                    "incident",
                    filter=Q(
                        incident__created_at__gte=date_from,
                    )
                    & Q(
                        incident__created_at__lte=date_to,
                    ),
                ),
                incidents_downtime=F("metric_subquery"),
                incident_uptime=Value(date_interval) - F("incidents_downtime"),
            )
            .annotate(**{
                field_name: Cast(
                    F("incident_uptime") / F("incident_count"),
                    output_field=DurationField(),
                )
            })
        )

    @staticmethod
    def search(
        queryset: QuerySet[Component] | None, search_term: str
    ) -> tuple[QuerySet[Component], bool]:
        # XXX Common search method
        if queryset is None:
            queryset = Component.objects.all()

        # If not search, return the original queryset
        if search_term is None or search_term.strip() == "":
            return queryset, False
        # Postgres search on title + description
        # XXX Improve search performance and relevance
        # XXX Support partial word search (infra matches infrastructure)
        vector = (
            SearchVector("name", config="english", weight="A")
            + SearchVector(
                "description",
                config="english",
                weight="B",
            )
            + SearchVector(
                "group__name",
                config="english",
                weight="C",
            )
            + SearchVector(
                "group__description",
                config="english",
                weight="D",
            )
        )
        query = SearchQuery(search_term, config="english", search_type="websearch")
        queryset = (
            queryset.annotate(rank=SearchRank(vector, query))
            .filter(rank__gte=0.01)
            .order_by("-rank")
        )

        return queryset, False


class Component(models.Model):
    objects: ComponentManager = ComponentManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    order = models.IntegerField(
        default=0,
        help_text="Order of the component in the list. Should be unique per `Group`.",
    )
    group = models.ForeignKey(Group, on_delete=models.PROTECT)
    private = models.BooleanField(
        default=False,
        help_text="If true, incident created with this component won't be communicated, and conversations will be made private. This is useful for sensitive components. In the future, private incidents may be visible only to its members.",
    )
    deploy_warning = models.BooleanField(
        default=True,
        help_text="If true, a warning will be sent when creating an incident of high severity with this component.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    if TYPE_CHECKING:
        # ruff: noqa: PLC0415
        if settings.ENABLE_SLACK:
            from firefighter.slack.models.conversation import Conversation
            from firefighter.slack.models.user_group import UserGroup

            usergroups: QuerySet[UserGroup]
            conversations: QuerySet[Conversation]

    class Meta(TypedModelMeta):
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{'🔒 ' if self.private else ''}{self.name}"

    def get_absolute_url(self) -> str:
        return reverse("incidents:component-detail", kwargs={"component_id": self.id})


class ComponentFilterSet(django_filters.FilterSet):
    """Set of filters for Component, share by Web UI and API."""

    id = django_filters.CharFilter(lookup_expr="iexact")
    private = django_filters.BooleanFilter()

    group = ModelMultipleChoiceFilter(
        queryset=Group.objects.order_by("order"),
        field_name="group_id",
        label="Group",
        widget=CustomCheckboxSelectMultiple,
    )
    metrics_period = FFDateRangeSingleFilterEmpty(
        method="metrics_period_filter",
        label="MTBF period",
    )
    search = django_filters.CharFilter(
        field_name="search", method="component_search", label="Search"
    )

    @staticmethod
    def component_search(
        queryset: QuerySet[Component], _name: str, value: str
    ) -> QuerySet[Component]:
        """Search incidents by title, description, and ID.

        Args:
            queryset (QuerySet[Component]): Queryset to search in.
            _name:
            value (str): Value to search for.

        Returns:
            QuerySet[Component]: Search results.
        """
        return Component.objects.search(queryset=queryset, search_term=value)[0]

    @staticmethod
    def metrics_period_filter(
        queryset: QuerySet[Component],
        _name: str,
        value: tuple[datetime, datetime, Any, Any],
    ) -> QuerySet[Component]:
        gte, lte, _, _ = value
        return Component.objects.queryset_with_mtbf(gte, lte, queryset=queryset)
