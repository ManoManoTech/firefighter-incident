"""Deferred re-sync of a corrected timeline, batched over a short window.

The timeline correction message saves every field on its own (see
`slack.views.modals.review_timeline.TimelineCorrection`), so syncing from the
save itself would mean one Jira round trip - and one "(edited)" refresh of the
Key Events message - per keystroke. Corrections schedule this task instead:
the first edit of a window arms it, the following ones ride along, and a single
sync runs once the reviewer is done typing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from celery import shared_task
from django.conf import settings
from django.core.cache import cache as dj_cache

from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import incident_key_events_updated

if TYPE_CHECKING:
    from django_redis.client.default import DefaultClient

cache = cast("DefaultClient", dj_cache)
logger = logging.getLogger(__name__)

_DEBOUNCE_KEY = "ff:timeline_sync:{incident_id}"
_DEFAULT_DEBOUNCE_SECONDS = 30
# The key is dropped as soon as the task runs; this margin only covers the case
# where the task never runs at all (no worker, lost message), so that a later
# correction can arm a new window instead of being silently swallowed.
_DEBOUNCE_KEY_MARGIN_SECONDS = 60


def _debounce_seconds() -> int:
    return int(
        getattr(
            settings, "FF_TIMELINE_SYNC_DEBOUNCE_SECONDS", _DEFAULT_DEBOUNCE_SECONDS
        )
    )


def schedule_timeline_sync(incident: Incident) -> bool:
    """Arm one deferred sync for this incident, or ride along an armed one.

    Returns whether this call armed the window. `cache.add` is the atomic
    check-and-set that makes concurrent edits (two people fixing different
    fields at once) schedule a single task rather than one each.
    """
    delay = _debounce_seconds()
    if not cache.add(
        _DEBOUNCE_KEY.format(incident_id=incident.id),
        1,
        timeout=delay + _DEBOUNCE_KEY_MARGIN_SECONDS,
    ):
        return False
    sync_corrected_timeline.apply_async((incident.id,), countdown=delay)
    return True


@shared_task(name="slack.sync_corrected_timeline")
def sync_corrected_timeline(incident_id: int) -> None:
    """Recompute metrics and push the corrected timeline to the post-mortem."""
    # Dropped first, so an edit made while this runs arms the next window
    # instead of being folded into a sync that already read the DB.
    cache.delete(_DEBOUNCE_KEY.format(incident_id=incident_id))

    incident = Incident.objects.filter(id=incident_id).first()
    if incident is None:
        logger.warning(
            "Skipping timeline sync for unknown incident #%s", incident_id
        )
        return

    incident.compute_metrics()
    # Refreshes the Key Events message and pushes the timeline to Jira - see
    # `jira_app.signals.sync_key_events_to_jira_postmortem`.
    incident_key_events_updated.send_robust(__name__, incident=incident)
    logger.info("Synced corrected timeline for incident #%s", incident_id)
