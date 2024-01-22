from __future__ import annotations

import logging

from celery import shared_task

from firefighter.pagerduty.models import PagerDutyTeam, PagerDutyUser
from firefighter.pagerduty.service import pagerduty_service
from firefighter.slack.models import SlackUser

logger = logging.getLogger(__name__)


@shared_task(name="pagerduty.fetch_users")
def fetch_users(*, delete_stale_user: bool = True) -> None:
    """Celery task to fetch PagerDuty users and save them in the database."""
    fetched_users_id = []
    for user in pagerduty_service.client.get_all_users():
        logger.debug(user)
        fetched_users_id.append(user["id"])
        main_user = SlackUser.objects.upsert_by_email(user["email"])
        if main_user is None:
            logger.warning("Could not find user with email %s", user["email"])
            continue

        phone_number = pagerduty_service.get_phone_number_from_body(user)
        if phone_number is None:
            phone_number = ""

        pd_user, _ = PagerDutyUser.objects.update_or_create(
            pagerduty_id=user["id"],
            defaults={
                "name": user["name"],
                "user": main_user,
                "phone_number": phone_number,
                "pagerduty_url": user["html_url"][:256],
                "pagerduty_api_url": user["self"][:256],
            },
        )
        pd_teams = user.get("teams", [])
        pd_teams_models: list[PagerDutyTeam] = []
        for pd_team in pd_teams:
            pd_team_model, _ = PagerDutyTeam.objects.update_or_create(
                pagerduty_id=pd_team["id"],
                defaults={
                    "name": pd_team["summary"],
                    "pagerduty_url": pd_team["html_url"][:256],
                    "pagerduty_api_url": pd_team["self"][:256],
                },
            )
            pd_teams_models.append(pd_team_model)

        pd_user.teams.set(pd_teams_models)

    # Check that we don't have stale users
    if len(fetched_users_id) != PagerDutyUser.objects.count():
        stale_user_ids = PagerDutyUser.objects.exclude(
            pagerduty_id__in=fetched_users_id
        ).values_list("pagerduty_id", flat=True)
        logger.info(f"Stale Pagerduty users found {list(stale_user_ids)}.")

        if delete_stale_user:
            nb_deleted, _ = PagerDutyUser.objects.filter(
                pagerduty_id__in=stale_user_ids
            ).delete()
            logger.info(f"Deleted {nb_deleted} stale PagerDuty users.")
