"""Celery settings definition."""

from __future__ import annotations

from firefighter.firefighter.settings.components.common import TIME_ZONE, USE_TZ
from firefighter.firefighter.settings.settings_utils import config

# Celery
# ------------------------------------------------------------------------------
timezone = "UTC"
if USE_TZ:
    timezone = TIME_ZONE

_CELERY_BROKER_URL = f'redis://{config("REDIS_HOST")}:{config("REDIS_PORT")}/10'

CELERY_SETTINGS = {
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-timezone
    "timezone": timezone,
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-broker_url
    "broker_url": _CELERY_BROKER_URL,
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-result_backend
    "result_backend": _CELERY_BROKER_URL,
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-accept_content
    "accept_content": ["json"],
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-task_serializer
    "task_serializer": "json",
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-result_serializer
    "result_serializer": "json",
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-time-limit
    # set to whatever value is adequate in your circumstances
    "task_time_limit": 3 * 60,  # in seconds
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-soft-time-limit
    "task_soft_time_limit": 2 * 60,  # in seconds
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#beat-scheduler
    "beat_scheduler": "django_celery_beat.schedulers:DatabaseScheduler",
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-broker_connection_retry
    "broker_connection_retry": True,
    "broker_connection_retry_on_startup": True,
}
