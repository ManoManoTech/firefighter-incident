from __future__ import annotations

import time

from celery import shared_task
from django.core.cache import caches

CELERY_HEARTBEAT_CACHE_KEY = "celery_heartbeat"
"""Cache key holding the Unix timestamp of the last heartbeat run by a worker."""


@shared_task(name="firefighter.celery_heartbeat", ignore_result=True)
def celery_heartbeat() -> None:
    """Record that a worker ran a task scheduled by beat.

    The readiness check reads this timestamp: a recent one proves that beat,
    the broker and at least one worker all work, end to end.
    """
    caches["default"].set(CELERY_HEARTBEAT_CACHE_KEY, time.time(), timeout=None)
