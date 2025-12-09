from __future__ import annotations

from django.conf import settings
from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.models.user import User


class JiraUser(models.Model):
    """Jira user model. It maps an [User][firefighter.incidents.models.user.User] with the Jira account id."""

    id = models.CharField(max_length=128, primary_key=True, editable=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="jira_user"
    )

    class Meta(TypedModelMeta):
        verbose_name = "Jira user"
        verbose_name_plural = "Jira users"

    def __str__(self) -> str:
        return f"{self.user}"


class JiraIssue(models.Model):
    """Jira issue model."""

    id = models.BigIntegerField(primary_key=True, editable=True)
    key = models.CharField[str, str](max_length=128)
    assignee = models.ForeignKey(
        JiraUser,
        on_delete=models.CASCADE,
        related_name="jira_ticket_assigned_set",
        null=True,
        blank=True,
    )
    reporter = models.ForeignKey(
        JiraUser, on_delete=models.CASCADE, related_name="jira_ticket_reporter_set"
    )
    issue_type = models.CharField(
        max_length=128,
        default="Incident",
    )
    project_key = models.CharField(
        max_length=128,
        default="INCIDENT",
    )
    watchers = models.ManyToManyField(
        User, related_name="jira_ticket_watchers_set", blank=True
    )

    description = models.TextField()

    summary = models.CharField(max_length=128, help_text="Title")

    class Meta(TypedModelMeta):
        verbose_name = "Jira issue"
        verbose_name_plural = "Jira issue"

    def __str__(self) -> str:
        return f"{self.key}: {self.summary}"


class JiraPostMortem(models.Model):
    """Jira Post-mortem linked to an Incident."""

    incident = models.OneToOneField(
        "incidents.Incident",
        on_delete=models.CASCADE,
        related_name="jira_postmortem_for",
        help_text="Incident this post-mortem is for",
    )

    jira_issue_key = models.CharField(
        max_length=32,
        unique=True,
        help_text="Jira issue key (e.g., INCIDENT-123)",
    )

    jira_issue_id = models.CharField(
        max_length=32,
        unique=True,
        help_text="Jira issue ID",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jira_postmortems_created",
    )

    class Meta(TypedModelMeta):
        db_table = "jira_postmortem"
        verbose_name = "Jira Post-mortem"
        verbose_name_plural = "Jira Post-mortems"

    def __str__(self) -> str:
        return (
            f"Jira Post-mortem {self.jira_issue_key} for incident #{self.incident.id}"
        )

    @property
    def issue_url(self) -> str:
        """Return Jira issue URL."""
        return f"{settings.RAID_JIRA_API_URL}/browse/{self.jira_issue_key}"
