from __future__ import annotations

import logging
import os
from typing import Any

from celery import Celery
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firefighter.firefighter.settings")


if os.environ.get("DD_TRACE_ENABLED", "false").lower() == "true":
    # Enable Datadog tracing except for dev env
    from ddtrace import patch

    patch(celery=True)


app = Celery("firefighter")


# Load task modules from all registered Django app configs.
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object(settings.CELERY_SETTINGS)

# Use our own logger (set by importing the settings)
# Log level is set when launching the worker
app.conf.worker_hijack_root_logger = False
app.autodiscover_tasks()


logger = logging.getLogger(__name__)


@app.task(bind=True)
def debug_task(self: Any) -> None:
    logger.info(f"Request: {self.request!r}")
