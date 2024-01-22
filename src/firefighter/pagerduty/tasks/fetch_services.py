from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from firefighter.pagerduty.models import PagerDutyService
from firefighter.pagerduty.service import pagerduty_service

logger = logging.getLogger(__name__)


@shared_task(name="pagerduty.fetch_services")
@transaction.atomic
def fetch_services() -> None:
    """Celery task to fetch PagerDuty services and save them in the database."""
    fetched_services_key = []
    for service in pagerduty_service.client.session.iter_all("services"):
        fetched_services_key.append(service["id"])
        PagerDutyService.objects.update_or_create(
            pagerduty_id=service["id"],
            defaults={
                "name": service["name"][:128],
                "status": service["status"][:128],
                "summary": service["summary"][:256],
                "web_url": service["html_url"][:256],
                "api_url": service["self"][:256],
            },
        )

    # Check that we don't have stale services
    if len(fetched_services_key) != PagerDutyService.objects.count():
        logger.warning("Stale PagerDuty Services found in DB. Manual action needed.")
        # XXX Delete stale services if we are confident enough
