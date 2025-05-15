from __future__ import annotations

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
