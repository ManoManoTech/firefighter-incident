"""Observability signals: emit structured log events for Datadog metrics and dashboards.

Listens to incident lifecycle signals and emits logs with consistent attributes
that Datadog can use for log-based metrics, facets, and dashboards.

Log attributes follow Datadog naming conventions:
- ff.metric: metric name (for log-based metric creation)
- ff.incident_id: incident ID
- ff.priority: priority value (1-5)
- ff.status: incident status
- ff.integration: integration name (jira, slack, confluence, pagerduty)
"""

from __future__ import annotations

import logging
from typing import Any

from django.dispatch import receiver

from firefighter.incidents.signals import (
    incident_closed,
    incident_created,
    incident_updated,
)

logger = logging.getLogger("firefighter.observability")


@receiver(signal=incident_created)
def log_incident_created(sender: Any, incident: Any, **kwargs: Any) -> None:
    logger.info(
        "Incident created: #%s [P%s] %s",
        incident.id,
        incident.priority.value,
        incident.title,
        extra={
            "ff.metric": "incident.created",
            "ff.incident_id": str(incident.id),
            "ff.priority": incident.priority.value,
            "ff.category": getattr(incident.incident_category, "name", "unknown"),
        },
    )


@receiver(signal=incident_closed)
def log_incident_closed(sender: Any, incident: Any, **kwargs: Any) -> None:
    logger.info(
        "Incident closed: #%s [P%s]",
        incident.id,
        incident.priority.value,
        extra={
            "ff.metric": "incident.closed",
            "ff.incident_id": str(incident.id),
            "ff.priority": incident.priority.value,
            "ff.status": str(incident.status),
        },
    )


@receiver(signal=incident_updated)
def log_incident_updated(sender: Any, incident: Any, **kwargs: Any) -> None:
    updated_fields: list[str] = kwargs.get("updated_fields", [])
    old_priority = kwargs.get("old_priority")

    if old_priority is not None and "priority_id" in updated_fields:
        new_priority = incident.priority.value
        direction = "escalated" if new_priority < old_priority.value else "deescalated"
        logger.info(
            "Incident %s: #%s P%s → P%s",
            direction,
            incident.id,
            old_priority.value,
            new_priority,
            extra={
                "ff.metric": f"incident.priority.{direction}",
                "ff.incident_id": str(incident.id),
                "ff.priority_old": old_priority.value,
                "ff.priority_new": new_priority,
            },
        )

    if "_status" in updated_fields:
        logger.info(
            "Incident status changed: #%s → %s",
            incident.id,
            incident.status,
            extra={
                "ff.metric": "incident.status_changed",
                "ff.incident_id": str(incident.id),
                "ff.status": str(incident.status),
                "ff.priority": incident.priority.value,
            },
        )
