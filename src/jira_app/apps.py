from __future__ import annotations

from django.apps import AppConfig


class JiraAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jira_app"
    verbose_name = "Jira"

    def ready(self) -> None:
        import jira_app.tasks

        return super().ready()
