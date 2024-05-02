from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.models.incident import Incident
from firefighter.jira_app.models import JiraIssue

if TYPE_CHECKING:
    from firefighter.incidents.models.impact import Impact  # noqa: F401


class JiraTicket(JiraIssue):
    """Jira ticket model."""

    # XXX Incident/Impact should be split into new models
    incident = models.OneToOneField(
        Incident, on_delete=models.CASCADE, related_name="jira_ticket", null=True
    )
    impacts = models.ManyToManyField["Impact", "JiraTicketImpact"](
        "incidents.Impact", through="JiraTicketImpact"
    )

    # TODO: priority
    # Jira Custom fields
    business_impact = models.CharField(
        max_length=128,
        help_text="It maps with customfield_10936",
        blank=True,
        null=True,
        default="",
    )

    class Meta(TypedModelMeta):
        verbose_name = "Jira ticket"
        verbose_name_plural = "Jira tickets"

    def get_absolute_url(self) -> str:
        return self.url

    @property
    def url(self) -> str:
        return f"{settings.RAID_JIRA_API_URL}/browse/{self.key}"


class JiraTicketImpact(models.Model):
    jira_ticket = models.ForeignKey[JiraTicket, JiraTicket](
        "JiraTicket", on_delete=models.CASCADE
    )
    impact = models.ForeignKey["Impact", "Impact"](
        "incidents.Impact", on_delete=models.CASCADE
    )

    def __str__(self) -> str:
        return f"{self.jira_ticket.key}: {self.impact}"


class RaidArea(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128)
    area = models.CharField(
        choices=(
            ("Sellers", "Sellers"),
            ("Internal", "Internal"),
            ("Customers", "Customers"),
        ),
        max_length=32,
    )

    class Meta(TypedModelMeta):
        unique_together = ("name", "area")

    def __str__(self) -> str:
        return self.name
