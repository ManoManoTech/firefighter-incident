from __future__ import annotations

import logging

from celery import shared_task
from jira.exceptions import JIRAError

from firefighter.raid.client import RAID_JIRA_PROJECT_KEY, client
from firefighter.raid.models import FeatureTeam

logger = logging.getLogger(__name__)


@shared_task(name="raid.check_feature_team_projects")
def check_feature_team_projects() -> None:
    """Log an error for each feature team whose Jira project cannot receive tickets.

    Jira projects get archived or restricted without Impact being told: the tickets
    of such a team silently fall back to the default project.
    """
    for team in FeatureTeam.objects.order_by("jira_project_key"):
        key = team.jira_project_key
        try:
            problem = client.get_project_creation_problem(key)
        except JIRAError:
            logger.exception(f"Could not check the Jira project {key} of feature team {team.name}")
            continue
        if problem:
            logger.error(
                f"Feature team {team.name} routes to Jira project {key}, which is {problem}: "
                f"its tickets fall back to {RAID_JIRA_PROJECT_KEY}. "
                "Update or remove this feature team."
            )
