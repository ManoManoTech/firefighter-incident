from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from pdpyras import PDClientError, PDHTTPError

from firefighter.incidents.models.incident import Incident
from firefighter.pagerduty.models import PagerDutyIncident, PagerDutyService
from firefighter.pagerduty.service import pagerduty_service

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User
logger = logging.getLogger(__name__)
APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME


@shared_task(name="pagerduty.trigger_oncall")
def trigger_oncall(
    oncall_service: PagerDutyService,
    title: str,
    details: str,
    incident_key: str,
    conference_url: str,
    incident_id: int | None = None,
    triggered_by: User | None = None,
) -> PagerDutyIncident:
    """Celery task to trigger an on-call in PagerDuty, from a FireFighter incident.

    XXX Trigger from PD user if it exists, instead of admin.
    XXX Should be a service ID instead of a service object.
    """
    service = oncall_service
    if incident_id:
        incident = Incident.objects.get(id=incident_id)
        details = f"""Triggered from {APP_DISPLAY_NAME} incident #{incident.id} {f"by {triggered_by.full_name}" if triggered_by else ""}
Priority: {incident.priority}
Environment: {incident.environment}
Incident category: {incident.incident_category.group.name} - {incident.incident_category.name}
FireFighter page: {incident.status_page_url + "?utm_medium=FireFighter+PagerDuty&utm_source=PagerDuty+Incident&utm_campaign=OnCall+Message+In+Channel"}
Slack channel #{incident.slack_channel_name}: {incident.slack_channel_url}

Incident Details:
{details}
"""
    try:
        res = pagerduty_service.client.create_incident(
            title=title,
            pagerduty_id=service.pagerduty_id,
            details=details,
            incident_key=incident_key,
            conference_url=conference_url,
        )

    except PDHTTPError as e:
        if e.response.status_code == 404:
            logger.exception("User not found")
        else:
            logger.exception("Transient network error: %s", e.msg)
            raise
    except PDClientError as e:
        logger.exception("Non-transient network or client error: %s", e.msg)
    # TODO Error handling

    if not 200 <= res.status_code < 300:
        logger.error({
            "message": "Error when calling PagerDuty API",
            "request": res.request.__dict__.get("body"),
            "response": res.json(),
        })
        err_msg = f"Error when calling PagerDuty API. {res.json()}"
        raise ValueError(err_msg)

    pd_incident = res.json()["incident"]

    pd_incident_db, _ = PagerDutyIncident.objects.update_or_create(
        incident_key=pd_incident["incident_key"],
        defaults={
            "title": pd_incident["title"][:128],
            "urgency": pd_incident["urgency"][:128],
            "incident_number": pd_incident["incident_number"],
            "status": pd_incident["status"][:128],
            "service_id": service.id,
            "details": pd_incident["body"]["details"][:3000],  # get_in
            "summary": pd_incident["summary"][:256],  # get_in
            "web_url": pd_incident["html_url"][:256],
            "api_url": pd_incident["self"][:256],
            "incident_id": incident_id,
        },
    )

    return pd_incident_db
