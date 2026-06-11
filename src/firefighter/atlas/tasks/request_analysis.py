"""Celery task: POST incident context to Atlas Bot for automated RCA."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    name="atlas.request_incident_analysis",
    bind=True,
    autoretry_for=(httpx.TransportError,),
    retry_kwargs={"max_retries": 3},
    default_retry_delay=30,
)
def request_incident_analysis(self: Any, incident_id: int, slack_channel_id: str) -> None:
    """POST incident context to Atlas Bot and trigger automated root-cause analysis.

    Fetches the incident from the DB, builds the payload, and calls the Atlas
    trigger endpoint.  Retries up to 3 times on transport/network errors; 5xx
    responses are also retried, 4xx responses fail permanently.

    The Atlas Bot will:
    1. Validate the shared secret.
    2. Async self-invoke its internal component to run a multi-track investigation.
    3. Post a ranked root-cause analysis (Block Kit) into ``slack_channel_id``.

    Args:
        self: Celery task instance (bound task).
        incident_id: PK of the ``Incident`` to analyse.
        slack_channel_id: Slack channel ID where Atlas should post the report.
    """
    shared_secret: str = settings.ATLAS_SHARED_SECRET
    if not shared_secret:
        logger.warning(
            "ATLAS_SHARED_SECRET is not configured — skipping Atlas analysis for incident %s",
            incident_id,
        )
        return

    from firefighter.firefighter.http_client import HttpClient
    from firefighter.incidents.models.incident import Incident

    incident = Incident.objects.select_related(
        "priority",
        "environment",
        "incident_category",
    ).get(id=incident_id)

    payload: dict[str, Any] = {
        "incident_id": str(incident.id),
        "priority": incident.priority.name,
        "title": incident.title,
        "description": incident.description,
        "category": incident.incident_category.name,
        # Atlas expects lowercase env values (prd / stg / int).
        "environment": incident.environment.value.lower(),
        "occurred_at": incident.created_at.isoformat(),
        "slack_channel_id": slack_channel_id,
    }

    atlas_url: str = settings.ATLAS_URL

    logger.info(
        "Posting incident analysis request to Atlas",
        extra={
            "incident_id": incident_id,
            "priority": incident.priority.name,
            "slack_channel_id": slack_channel_id,
            "atlas_url": atlas_url,
        },
    )

    response = HttpClient().post(
        atlas_url,
        json=payload,
        headers={"X-Atlas-Secret": shared_secret},
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise self.retry(exc=exc) from exc
        logger.exception(
            "Atlas rejected incident analysis request permanently",
            extra={
                "incident_id": incident_id,
                "status_code": exc.response.status_code,
            },
        )
        return

    logger.info(
        "Atlas accepted incident analysis request",
        extra={
            "incident_id": incident_id,
            "status_code": response.status_code,
            "slack_channel_id": slack_channel_id,
        },
    )
