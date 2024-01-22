from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from firefighter.firefighter.celery_client import app as celery_app
from firefighter.pagerduty.models import (
    PagerDutyEscalationPolicy,
    PagerDutyOncall,
    PagerDutySchedule,
    PagerDutyService,
    PagerDutyUser,
)
from firefighter.pagerduty.service import pagerduty_service

logger = logging.getLogger(__name__)


@celery_app.task(name="pagerduty.fetch_oncalls")
def fetch_oncalls() -> None:
    """Celery task to fetch PagerDuty oncalls and save them in the database.
    Will try to update services, users, schedules and escalation policies if needed.
    """
    services = pagerduty_service.get_all_oncalls()
    return create_oncalls(services)


@transaction.atomic
def create_oncalls(oncalls: list[dict[str, Any]]) -> None:
    new_oncalls_ids = set()

    for oncall in oncalls:
        start = oncall["start"]
        end = oncall["end"]
        escalation_level = oncall["escalation_level"]
        escalation_policy_data = oncall.get("escalation_policy", None)
        user_data = oncall.get("user", None)
        schedule_data = oncall.get("schedule", None)
        if user_data is None:
            logger.warning("No user found for oncall %s", oncall)
            continue

        if escalation_policy_data is None:
            logger.warning("No escalation policy found for oncall %s", oncall)
            continue

        (
            escalation_policy,
            _escalation_policy_added,
        ) = PagerDutyEscalationPolicy.objects.update_or_create(
            pagerduty_id=escalation_policy_data["id"],
            defaults={
                "name": escalation_policy_data["name"][:128],
                "summary": escalation_policy_data["summary"][:256],
                "pagerduty_url": escalation_policy_data["html_url"][:256],
                "pagerduty_api_url": escalation_policy_data["self"][:256],
            },
        )
        services_data = escalation_policy_data.get("services", [])

        if len(services_data) > 0:
            for service_datum in services_data:
                _, _ = PagerDutyService.objects.update_or_create(
                    pagerduty_id=service_datum["id"],
                    defaults={"escalation_policy": escalation_policy},
                )
        # We can have an Oncall user with no schedule, e.g. when the user is defined in an escalation policy's escalation_rule
        if schedule_data is not None:
            schedule, _schedule_added = PagerDutySchedule.objects.update_or_create(
                pagerduty_id=schedule_data["id"],
                defaults={
                    "summary": schedule_data["summary"][:256],
                    "pagerduty_url": schedule_data["html_url"][:256],
                    "pagerduty_api_url": schedule_data["self"][:256],
                },
            )
        else:
            schedule = None
        user = PagerDutyUser.objects.upsert_by_pagerduty_id(
            pagerduty_id=user_data["id"],
            email=user_data["email"],
            phone_number="",
            name=user_data["name"],
        )
        if user is None:
            logger.warning("No user found for oncall %s", oncall)
            continue
        pagerduty_user = user.pagerduty_user

        oncall_final, _oncall_final_added = PagerDutyOncall.objects.update_or_create(
            pagerduty_user=pagerduty_user,
            schedule=schedule,
            escalation_policy=escalation_policy,
            start=start,
            end=end,
            escalation_level=escalation_level,
        )
        new_oncalls_ids.add(oncall_final.id)

    for stale_oncall in PagerDutyOncall.objects.exclude(
        id__in=new_oncalls_ids,
    ).filter(start__lte=timezone.now(), end__gte=timezone.now()):
        if stale_oncall.id not in new_oncalls_ids:
            stale_oncall.delete()
