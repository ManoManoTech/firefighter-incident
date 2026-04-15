"""Disable Confluence periodic tasks when ENABLE_CONFLUENCE is False.

Confluence tasks were previously added manually via Django admin.
When the Confluence app is disabled, the worker doesn't register these tasks,
but Celery Beat (DatabaseScheduler) still dispatches them, causing
"Received unregistered task" errors.

This migration disables all Confluence periodic tasks when the app is not enabled,
and re-enables them on rollback (assuming Confluence would be re-enabled).
"""

from __future__ import annotations

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

CONFLUENCE_TASK_PREFIX = "confluence."


def disable_confluence_tasks_if_not_enabled(apps, schema_editor):
    from django.conf import settings

    if getattr(settings, "ENABLE_CONFLUENCE", False):
        return

    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    updated = PeriodicTask.objects.filter(
        task__startswith=CONFLUENCE_TASK_PREFIX,
        enabled=True,
    ).update(enabled=False)

    if updated:
        logger.info("Disabled %d Confluence periodic task(s) (ENABLE_CONFLUENCE=False)", updated)


def re_enable_confluence_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    updated = PeriodicTask.objects.filter(
        task__startswith=CONFLUENCE_TASK_PREFIX,
        enabled=False,
    ).update(enabled=True)

    if updated:
        logger.info("Re-enabled %d Confluence periodic task(s)", updated)


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0031_remove_incident_incidents_incident_closure_reason_valid_and_more"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            disable_confluence_tasks_if_not_enabled,
            reverse_code=re_enable_confluence_tasks,
        ),
    ]
