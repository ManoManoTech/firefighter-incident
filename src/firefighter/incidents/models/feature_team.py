from __future__ import annotations

from django.db import models
from django_stubs_ext.db.models import TypedModelMeta


class FeatureTeam(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=80)
    jira_project_key = models.CharField(
        max_length=10,
        unique=True,
    )

    class Meta(TypedModelMeta):
        unique_together = ("name", "jira_project_key")

    def __str__(self) -> str:
        return self.name

    @property
    def get_team(self) -> str:
        return "{self.name}  {self.jira_project_key}"

    @property
    def get_key(self) -> str:
        return "{self.jira_project_key}"
