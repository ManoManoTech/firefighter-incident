from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from jira.exceptions import JIRAError

from firefighter.raid.models import FeatureTeam
from firefighter.raid.tasks.check_feature_team_projects import (
    check_feature_team_projects,
)


@pytest.mark.django_db
class TestCheckFeatureTeamProjects:
    @staticmethod
    def _run(problems: dict[str, str | Exception | None]) -> None:
        def get_problem(key: str) -> str | None:
            outcome = problems[key]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch(
            "firefighter.raid.tasks.check_feature_team_projects.client.get_project_creation_problem",
            side_effect=get_problem,
        ):
            check_feature_team_projects()

    def test_logs_an_error_per_broken_feature_team(self, caplog: pytest.LogCaptureFixture) -> None:
        FeatureTeam.objects.create(name="Customer Activation", jira_project_key="UP")
        FeatureTeam.objects.create(name="Data", jira_project_key="DATA")

        with caplog.at_level(logging.INFO):
            self._run({"UP": "archived", "DATA": None})

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "Customer Activation" in errors[0].getMessage()
        assert "UP, which is archived" in errors[0].getMessage()

    def test_logs_nothing_when_every_project_accepts_tickets(self, caplog: pytest.LogCaptureFixture) -> None:
        FeatureTeam.objects.create(name="Data", jira_project_key="DATA")

        self._run({"DATA": None})

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_keeps_checking_after_a_jira_error(self, caplog: pytest.LogCaptureFixture) -> None:
        FeatureTeam.objects.create(name="Acquisition", jira_project_key="AMT")
        FeatureTeam.objects.create(name="Security", jira_project_key="SEC")

        self._run({"AMT": JIRAError(status_code=500, text="Jira down"), "SEC": "not found"})

        messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert any("Could not check the Jira project AMT" in m for m in messages)
        assert any("Feature team Security routes to Jira project SEC" in m for m in messages)


@pytest.mark.django_db
def test_check_is_scheduled_every_monday_morning() -> None:
    from django_celery_beat.models import PeriodicTask

    task = PeriodicTask.objects.get(task="raid.check_feature_team_projects")
    assert task.enabled
    assert (task.crontab.minute, task.crontab.hour, task.crontab.day_of_week) == ("0", "9", "1")
    assert str(task.crontab.timezone) == "Europe/Paris"
