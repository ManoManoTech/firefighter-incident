from __future__ import annotations

import logging
from datetime import datetime, timedelta
from functools import reduce
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.fields import FloatField, IntegerField
from django.db.models.functions import Cast
from django.template.defaultfilters import floatformat
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models import Group, Incident, Priority
from firefighter.incidents.models.metric_type import IncidentMetric
from firefighter.incidents.views.date_filter import get_date_range_from_special_date
from firefighter.incidents.views.date_utils import get_biggest_date

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django.http.request import HttpRequest
    from django_stubs_ext import WithAnnotations
logger = logging.getLogger(__name__)


def weekly_dashboard_context(
    request: HttpRequest, incidents: QuerySet[Incident]
) -> dict[str, Any]:
    logger.debug(request)

    # Dates for our queries
    date_gte, date_lte, date_str, date_input = get_date_range_from_parameters(request)

    if date_input and not (date_gte or date_lte):
        messages.error(request, "Invalid date range.")

    incident_by_priority, incident_by_priority_total_row = get_incident_by_priority(
        incidents
    )

    incident_age_by_priority = get_incident_age_by_priority(
        incidents, date_lte, date_gte
    )
    (
        incident_ttr_by_priority_total_row,
        incident_ttr_by_priority,
    ) = get_incident_time_to_by_priority(incidents)

    incidents_by_domain = get_incidents_by_domain(incidents)

    incidents_by_priority_chart = {
        "keys": [x.name for x in incident_by_priority],
        "values": [x.incident_total for x in incident_by_priority],
    }
    incidents_by_domain_chart = {
        "keys": [x.name for x in incidents_by_domain],
        "values": [x.incidents_nb for x in incidents_by_domain],
    }
    incident_by_status_chart = get_incident_by_status_chart_data(incidents)

    incident_by_priority_table = {
        "cols": ["Priority", "Total", "Opened", "Closed", "Closed %"],
        "body": {
            "objects": incident_by_priority,
            "format": [
                {"filter": None, "suffix": None, "key": "name"},
                {"filter": floatformat, "suffix": None, "key": "incident_total"},
                {"filter": floatformat, "suffix": None, "key": "incident_open"},
                {"filter": floatformat, "suffix": None, "key": "incident_closed"},
                {
                    "filter": floatformat,
                    "filter_args": 2,
                    "suffix": "%",
                    "key": "incident_closed_percentage",
                },
            ],
        },
        "footer": incident_by_priority_total_row,
    }

    # TODO Improve table template to allow cell customization (link)
    incident_age_by_priority_table = {
        "cols": [
            "Priority",
            "0-2 days",
            "3-4 days",
            "5-6 days",
            "7-14 days",
            "15-29 days",
            "30-89 days",
            "90+ days",
        ],
        "body": {
            "objects": incident_age_by_priority,
            "format": [
                {"key": "name"},
                {"key": "incident_0_3_label"},
                {"key": "incident_3_5_label"},
                {"key": "incident_5_7_label"},
                {"key": "incident_7_15_label"},
                {"key": "incident_15_30_label"},  # gitleaks:allow
                {"key": "incident_30_90_label"},
                {"key": "incident_gt_90_label"},
            ],
        },
    }

    incident_ttr_by_priority_percentage_table = {
        "cols": ["Priority", "< 15m", "< 30m", "< 1h", "< 3h", "< 1d", "≥ 1d"],
        "body": {
            "objects": incident_ttr_by_priority,
            "format": [
                {"filter": None, "suffix": None, "key": "name"},
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_lt_15m_perc",
                },
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_lt_30m_perc",
                },
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_lt_1h_perc",
                },
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_lt_3h_perc",
                },
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_lt_1d_perc",
                },
                {
                    "filter": floatformat,
                    "filter_args": 1,
                    "suffix": "%",
                    "key": "ttr_gte_1d_perc",
                },
            ],
        },
    }

    incident_ttr_by_priority_table = {
        "cols": ["Priority", "< 15m", "< 30m", "< 1h", "< 3h", "< 1d", "≥ 1d"],
        "body": {
            "objects": incident_ttr_by_priority,
            "format": [
                {"filter": None, "suffix": None, "key": "name"},
                {"filter": floatformat, "key": "ttr_lt_15m"},
                {"filter": floatformat, "key": "ttr_lt_30m"},
                {"filter": floatformat, "key": "ttr_lt_1h"},
                {"filter": floatformat, "key": "ttr_lt_3h"},
                {"filter": floatformat, "key": "ttr_lt_1d"},
                {"filter": floatformat, "key": "ttr_gte_1d"},
            ],
        },
        "footer": incident_ttr_by_priority_total_row,
    }

    return {
        "incident_by_priority_table": incident_by_priority_table,
        "incident_age_by_priority_table": incident_age_by_priority_table,
        "incident_ttr_by_priority_percentage_table": incident_ttr_by_priority_percentage_table,
        "incident_ttr_by_priority_table": incident_ttr_by_priority_table,
        "incident_by_priority": incident_by_priority,
        "incident_ttr_by_priority": incident_ttr_by_priority,
        "incident_ttr_by_priority_total_row": incident_ttr_by_priority_total_row,
        "incident_age_by_priority": incident_age_by_priority,
        "incident_by_status_chart": incident_by_status_chart,
        "incident_by_domain_chart": incidents_by_domain_chart,
        "incident_by_priority_chart": incidents_by_priority_chart,
        "page_title": "Reports",
        "date_gte": date_gte,
        "date_lte": date_lte,
        "date_str": date_str,
        "date_input": date_input,
    }


def get_incident_age_by_priority(
    incidents: QuerySet[Incident], date_lte: datetime | None, date_gte: datetime | None
) -> QuerySet[Priority]:
    j_3 = timezone.now() + relativedelta(days=-3)
    j_5 = timezone.now() + relativedelta(days=-5)
    j_7 = timezone.now() + relativedelta(days=-7)
    j_15 = timezone.now() + relativedelta(days=-15)
    j_30 = timezone.now() + relativedelta(days=-30)
    j_90 = timezone.now() + relativedelta(days=-90)

    incident_age_by_priority_q = Q(incident___status__lt=IncidentStatus.CLOSED) & Q(
        incident__in=incidents
    )

    incident_age_by_priority = Priority.objects.order_by("value").annotate(
        incident_0_3=Count(
            "incident",
            filter=(incident_age_by_priority_q & Q(incident__created_at__gt=j_3)),
            output_field=IntegerField(),
        ),
        incident_3_5=Count(
            "incident",
            filter=(
                incident_age_by_priority_q
                & Q(incident__created_at__lt=j_3)
                & Q(incident__created_at__gte=j_5)
            ),
            output_field=IntegerField(),
        ),
        incident_5_7=Count(
            "incident",
            filter=(
                incident_age_by_priority_q
                & Q(incident__created_at__lt=j_5)
                & Q(incident__created_at__gte=j_7)
            ),
            output_field=IntegerField(),
        ),
        incident_7_15=Count(
            "incident",
            filter=(
                incident_age_by_priority_q
                & Q(incident__created_at__lt=j_7)
                & Q(incident__created_at__gte=j_15)
            ),
            output_field=IntegerField(),
        ),
        incident_15_30=Count(
            "incident",
            filter=(
                incident_age_by_priority_q
                & Q(incident__created_at__lt=j_15)
                & Q(incident__created_at__gte=j_30)
            ),
            output_field=IntegerField(),
        ),
        incident_30_90=Count(
            "incident",
            filter=(
                incident_age_by_priority_q
                & Q(incident__created_at__lt=j_30)
                & Q(incident__created_at__gte=j_90)
            ),
            output_field=IntegerField(),
        ),
        incident_gt_90=Count(
            "incident",
            filter=(incident_age_by_priority_q & Q(incident__created_at__lte=j_90)),
            output_field=IntegerField(),
        ),
        incident_0_3_label=Value(""),
        incident_3_5_label=Value(""),
        incident_5_7_label=Value(""),
        incident_7_15_label=Value(""),
        incident_15_30_label=Value(""),
        incident_30_90_label=Value(""),
        incident_gt_90_label=Value(""),
    )

    common_params = f"&_status__lt={IncidentStatus.CLOSED.value}"
    date_gte_param = f"{f'&created__lte={date_lte}' if date_lte else ''}"
    # pyright: reportGeneralTypeIssues=false
    for sev in incident_age_by_priority:
        sev.incident_0_3_label = f'<a class="{"underline" if sev.incident_0_3 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_3, None, date_gte)}{common_params}">{sev.incident_0_3}</a>'
        sev.incident_3_5_label = f'<a class="{"underline" if sev.incident_3_5 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_5, j_3, date_gte)}{common_params}">{sev.incident_3_5}</a>'
        sev.incident_5_7_label = f'<a class="{"underline" if sev.incident_5_7 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_7, j_15, date_gte)}{common_params}">{sev.incident_5_7}</a>'
        sev.incident_7_15_label = f'<a class="{"underline" if sev.incident_7_15 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_15, j_7, date_gte)}{common_params}">{sev.incident_7_15}</a>'
        sev.incident_15_30_label = f'<a class="{"underline" if sev.incident_15_30 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_30, j_15, date_gte)}{common_params}">{sev.incident_15_30}</a>'
        sev.incident_30_90_label = f'<a class="{"underline" if sev.incident_30_90 else "opacity-50"}" href="/incident/?priority={sev.id}{get_created_at_filter(j_90, j_30, date_gte)}{common_params}">{sev.incident_30_90}</a>'
        sev.incident_gt_90_label = f'<a class="{"underline" if sev.incident_gt_90 else "opacity-50"}" href="/incident/?priority={sev.id}&created_at=2000+-+{str(j_90).replace("-", "/")}{date_gte_param}{common_params}">{sev.incident_gt_90}</a>'

    return incident_age_by_priority


def get_created_at_filter(
    date_gte: datetime, date_lt: datetime | None, date_gte_global: datetime | None
) -> str:
    return f'&created_at={str(get_biggest_date(date_gte_global, date_gte).isoformat()).replace("-", "/").replace("+", "%2B")}+-+{str(date_lt.isoformat()).replace("-", "/").replace("+", "%2B") if date_lt else "now"}'


class _IncidentPriorityAnnotation(TypedDict):
    incident_total: int
    incident_closed: float
    incident_open: float
    incident_closed_percentage: NotRequired[float]


def get_incident_by_priority(
    incidents: QuerySet[Incident],
) -> tuple[
    QuerySet[WithAnnotations[Priority, _IncidentPriorityAnnotation]],
    dict[str, str | float | int],
]:
    incident_by_priority = (
        Priority.objects.order_by("value")
        .filter(incident__in=incidents)
        .annotate(
            incident_total=Count("incident"),  # (len(incidents)),
            incident_closed=Count(
                "incident",
                filter=Q(incident___status=IncidentStatus.CLOSED),
                output_field=FloatField(),
            ),
            incident_open=Count(
                "incident",
                filter=Q(incident___status__lt=IncidentStatus.CLOSED),
                output_field=FloatField(),
            ),
        )
        .filter(incident_total__gt=0.0)
        .annotate(
            incident_closed_percentage=(
                Cast(F("incident_closed"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            )
        )
    )

    # Add the total row
    incident_by_priority_total_row: dict[str, str | float | int] = {"name": "Total"}
    for key in [
        "incident_closed",
        "incident_open",
        "incident_total",
    ]:
        incident_by_priority_total_row[key] = reduce(
            (lambda tot, x: tot + x.__dict__[key]), incident_by_priority, 0
        )

    if incident_by_priority_total_row.get("incident_total") != 0:
        closed = int(incident_by_priority_total_row.get("incident_closed", 0))
        total = incident_by_priority_total_row.get("incident_total")
        if not isinstance(closed, int) or not isinstance(total, int):
            raise ValueError("Invalid type for closed or total")
        incident_by_priority_total_row["incident_closed_percentage"] = (
            closed / total * 100
        )
    return incident_by_priority, incident_by_priority_total_row  # type: ignore[return-value]


class _IncidentByDomainAnnotation(TypedDict):
    incidents_nb: int | float


def get_incidents_by_domain(
    incidents: QuerySet[Incident],
) -> QuerySet[WithAnnotations[Group, _IncidentByDomainAnnotation]]:
    return Group.objects.filter(incidentcategory__incident__in=incidents).annotate(
        incidents_nb=Count("incidentcategory__incident", output_field=FloatField()),
    )


def get_incident_time_to_by_priority(
    incidents: QuerySet[Incident], time_to: str = "time_to_fix"
) -> tuple[dict[str, str], QuerySet[Priority]]:
    ttr_q = (
        Q(incident___status__gte=IncidentStatus.MITIGATED)
        & Q(metric_type__type=time_to)
        & Q(duration__gte=timedelta(seconds=1))
        & Q(incident__in=incidents)
    )
    metric_subquery = (
        IncidentMetric.objects.filter(ttr_q)
        .values("incident__priority")
        .annotate(
            incident_total=Count("incident", output_field=FloatField()),
            ttr_lt_15m=Count(
                "incident",
                filter=Q(duration__lt=timedelta(minutes=15)),
                output_field=FloatField(),
            ),
            ttr_lt_30m=Count(
                "incident",
                filter=Q(duration__lt=timedelta(minutes=30)),
                output_field=FloatField(),
            ),
            ttr_lt_1h=Count(
                "incident",
                filter=Q(duration__lt=timedelta(minutes=60)),
                output_field=FloatField(),
            ),
            ttr_lt_3h=Count(
                "incident",
                filter=Q(duration__lt=timedelta(hours=3)),
                output_field=FloatField(),
            ),
            ttr_lt_1d=Count(
                "incident",
                filter=Q(duration__lt=timedelta(days=1)),
                output_field=FloatField(),
            ),
            ttr_gte_1d=Count(
                "incident",
                filter=Q(duration__gte=timedelta(days=1)),
                output_field=FloatField(),
            ),
        )
    )

    incident_ttr_by_priority = (
        Priority.objects.order_by("value")
        .annotate(
            incident_total=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "incident_total"
                )[:1]
            ),
            ttr_lt_15m=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_lt_15m"
                )[:1]
            ),
            ttr_lt_30m=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_lt_30m"
                )[:1]
            ),
            ttr_lt_1h=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_lt_1h"
                )[:1]
            ),
            ttr_lt_3h=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_lt_3h"
                )[:1]
            ),
            ttr_lt_1d=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_lt_1d"
                )[:1]
            ),
            ttr_gte_1d=Subquery(
                metric_subquery.filter(incident__priority=OuterRef("pk")).values(
                    "ttr_gte_1d"
                )[:1]
            ),
        )
        .filter(incident_total__gt=0.0)
        .annotate(
            ttr_lt_15m_perc=(
                Cast(F("ttr_lt_15m"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
            ttr_lt_30m_perc=(
                Cast(F("ttr_lt_30m"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
            ttr_lt_1h_perc=(
                Cast(F("ttr_lt_1h"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
            ttr_lt_3h_perc=(
                Cast(F("ttr_lt_3h"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
            ttr_lt_1d_perc=(
                Cast(F("ttr_lt_1d"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
            ttr_gte_1d_perc=(
                Cast(F("ttr_gte_1d"), FloatField())
                / Cast(F("incident_total"), FloatField())
                * 100.0
            ),
        )
    )
    incident_ttr_by_priority_total_row = {"name": "Total"}
    for key in [
        "ttr_lt_15m",
        "ttr_lt_30m",
        "ttr_lt_1h",
        "ttr_lt_3h",
        "ttr_lt_1d",
        "ttr_gte_1d",
        "incident_total",
    ]:
        incident_ttr_by_priority_total_row[key] = str(
            reduce(
                (lambda total, x: total + x.__dict__[key]), incident_ttr_by_priority, 0
            )
        )
    return incident_ttr_by_priority_total_row, incident_ttr_by_priority


def get_incident_by_status_chart_data(
    incidents: QuerySet[Incident],
) -> dict[str, list[Any]]:
    incident_by_status = incidents.aggregate(
        incident_open=Count(
            "_status",
            filter=Q(_status=IncidentStatus.OPEN),
            output_field=FloatField(),
        ),
        incident_investigating=Count(
            "_status",
            filter=Q(_status=IncidentStatus.INVESTIGATING),
            output_field=FloatField(),
        ),
        incident_fixing=Count(
            "_status",
            filter=Q(_status=IncidentStatus.MITIGATING),
            output_field=FloatField(),
        ),
        incident_fixed=Count(
            "_status",
            filter=Q(_status=IncidentStatus.MITIGATED),
            output_field=FloatField(),
        ),
        incident_postmortem=Count(
            "_status",
            filter=Q(_status=IncidentStatus.POST_MORTEM),
            output_field=FloatField(),
        ),
        incident_closed=Count(
            "_status",
            filter=Q(_status=IncidentStatus.CLOSED),
            output_field=FloatField(),
        ),
        incident_total=Count(
            "_status",
            output_field=FloatField(),
        ),
    )
    if incident_by_status.get("incident_total") == 0:
        return {
            "keys": [],
            "values": [],
        }
    val = list(incident_by_status.values())
    val.pop(6)
    return {
        "keys": list(IncidentStatus.labels),
        "values": val,
    }


def get_date_range_from_parameters(
    request: HttpRequest,
) -> tuple[datetime | None, datetime | None, str | None, str | None]:
    unparsed_date = request.GET.get("created_at")
    if not unparsed_date:
        return None, None, None, None

    return get_date_range_from_special_date(unparsed_date)
