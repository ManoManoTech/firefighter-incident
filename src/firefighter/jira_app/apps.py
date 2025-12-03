from __future__ import annotations

from django.apps import AppConfig


class JiraAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "jira_app"
    name = "firefighter.jira_app"
    verbose_name = "Jira"

    def ready(self) -> None:
        # Register signals
        # E.g. usage: create PostMortem (Jira and/or Confluence) on incident_updated
        import firefighter.jira_app.signals
        import firefighter.jira_app.tasks

        return super().ready()
