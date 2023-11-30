from __future__ import annotations

from django.apps import AppConfig


class JiraAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "jira_app"
    name = "firefighter.jira_app"
    verbose_name = "Jira"

    def ready(self) -> None:
        import firefighter.jira_app.tasks

        return super().ready()
