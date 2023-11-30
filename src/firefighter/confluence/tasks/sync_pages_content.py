from __future__ import annotations

import logging

from celery import shared_task

from firefighter.confluence.models import ConfluencePage
from firefighter.confluence.service import confluence_service
from firefighter.firefighter.utils import get_in

logger = logging.getLogger(__name__)


@shared_task(
    name="confluence.sync_pages_content", soft_time_limit=60 * 5, time_limit=60 * 7
)
def sync_pages_content() -> None:
    for runbook in ConfluencePage.objects.all():
        res = confluence_service.get_page_with_body_and_version(runbook.page_id)
        # Check if the page still exists, if not, delete it
        if res.get("statusCode", None) == 404 and get_in(res, ["data", "authorized"]):
            logger.info(f"Page {runbook.page_id} {runbook} not found, deleting it")
            runbook.delete()
            continue

        body = res.get("body", None)
        if body is None:
            logger.warning("No body found for page %s", runbook)
            continue
        runbook.body_export_view = get_in(res, ["body", "export_view", "value"])
        runbook.body_storage = get_in(res, ["body", "storage", "value"])
        runbook.body_view = get_in(res, ["body", "view", "value"])
        runbook.version = get_in(res, ["version"], {})
        runbook.save()
