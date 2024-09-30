from __future__ import annotations

import logging
import textwrap
import uuid
from typing import TYPE_CHECKING, ClassVar

import django_filters
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models
from django.urls import reverse
from django_filters.filters import AllValuesMultipleFilter

from firefighter.confluence.service import confluence_service
from firefighter.firefighter.fields_forms_widgets import CustomCheckboxSelectMultiple
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import postmortem_created

if TYPE_CHECKING:
    from django.db.models import QuerySet
logger = logging.getLogger(__name__)


class PostMortemManager(models.Manager["PostMortem"]):
    @staticmethod
    def create_postmortem_for_incident(incident: Incident) -> PostMortem:
        if hasattr(incident, "postmortem_for"):
            raise ValueError("Incident already has a post-mortem page")

        logger.info("Creating PostMortem for %s", incident)

        topic_prefix = (
            ""
            if settings.ENV in {"support", "prod"}
            else f"[IGNORE - TEST {settings.ENV}] "
        )

        postmortem_topic = f"{topic_prefix}#{incident.slack_channel_name} ({incident.priority.name}) {incident.title}"
        postmortem_topic = textwrap.shorten(
            postmortem_topic, width=250, placeholder="..."
        )

        pm = confluence_service.create_postmortem(postmortem_topic)

        # TODO More error checking on this side
        if not pm:
            logger.warning("Could not create PostMortem for %s. Empty body.", incident)
            raise ValueError(
                "Could not create PostMortem for incident. Empty body from Confluence."
            )

        page_info = confluence_service.parse_confluence_page(pm)

        pm_page = PostMortem(
            incident=incident,
            **page_info,
        )
        pm_page.save()

        postmortem_created.send_robust(sender=__name__, incident=incident)

        previous_postmortem = (
            PostMortem.objects.exclude(id=pm_page.id)
            .exclude(incident__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if previous_postmortem:
            confluence_service.move_page(
                int(pm_page.page_id),
                int(previous_postmortem.page_id),
                position="before",
            )

        return pm_page


class ConfluencePage(models.Model):
    """Represents a Confluence page."""

    objects: ClassVar[models.Manager[ConfluencePage]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    page_id = models.PositiveBigIntegerField(db_index=True, unique=True)
    page_url = models.URLField(max_length=1024)
    page_edit_url = models.URLField(max_length=1024)
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When was the DB record created, not when the page was created on Confluence.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When was the DB record updated, not when the page was created on Confluence.",
    )

    # XXX view and export_view may be redundant
    body_storage = models.TextField(null=True, blank=True)
    body_view = models.TextField(null=True, blank=True)
    body_export_view = models.TextField(null=True, blank=True)

    version = models.JSONField(default=dict)  # We need a callable

    def __str__(self) -> str:
        return self.name


class PostMortem(ConfluencePage):
    """Represents a Confluence PostMortem page."""

    objects: ClassVar[PostMortemManager] = PostMortemManager()

    incident = models.OneToOneField(
        Incident, on_delete=models.CASCADE, related_name="postmortem_for"
    )

    def __str__(self) -> str:
        return self.name


class RunbookManager(models.Manager["Runbook"]):
    @staticmethod
    def search(
        queryset: QuerySet[Runbook] | None, search_term: str
    ) -> tuple[QuerySet[Runbook], bool]:
        """Args:
            queryset (QuerySet[Runbook] | None): Queryset to search in. If None, search in all incidents. The Queryset allows to search on a subset of Runbooks (already filtered).
            search_term (str): Search term.

        Returns:
            tuple[QuerySet[Runbook], bool]: Queryset of Runbooks matching the search term, and a boolean indicating if the search may contain duplicates objects.
        """
        if queryset is None:
            queryset = Runbook.objects.all()

        # If not search, return the original queryset
        if search_term is None or search_term.strip() == "":
            return queryset, False

        # XXX Improve search performance and relevance
        vector = (
            SearchVector("name", config="english", weight="A")
            + SearchVector("service_name", config="english", weight="B")
            + SearchVector("body_storage", config="english", weight="C")
        )
        query = SearchQuery(search_term, config="english", search_type="websearch")
        queryset = (
            queryset.annotate(rank=SearchRank(vector, query))
            .filter(rank__gte=0.05)
            .order_by("-rank")
        )

        return queryset, False


class Runbook(ConfluencePage):
    objects: ClassVar[RunbookManager] = RunbookManager()

    title = models.CharField(max_length=255)
    service_name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("confluence:runbook_details", kwargs={"runbook_id": self.id})


class RunbookFilterSet(django_filters.FilterSet):
    """Set of filters for Runbooks."""

    id = django_filters.CharFilter(lookup_expr="iexact")
    service_type = AllValuesMultipleFilter(
        label="Service Type",
        field_name="service_type",
        widget=CustomCheckboxSelectMultiple,
        null_value="All Types",
    )

    search = django_filters.CharFilter(
        field_name="search", method="runbook_search", label="Search"
    )

    @staticmethod
    def runbook_search(
        queryset: QuerySet[Runbook], _name: str, value: str
    ) -> QuerySet[Runbook]:
        return Runbook.objects.search(queryset=queryset, search_term=value)[0]
