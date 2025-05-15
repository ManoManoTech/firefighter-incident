from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, cast

from celery import shared_task
from django.db.utils import IntegrityError

from firefighter.confluence.models import Runbook
from firefighter.confluence.service import confluence_service

if TYPE_CHECKING:
    from firefighter.confluence.utils import ConfluencePageId

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "ms",
    "front",
    "infra",
    "app",
    "other",
    "task",
    "stream",
    "site",
    "msf",
    "data",
    "gw",
    "nbk",
    "external",
}


@shared_task(name="confluence.sync_runbooks")
def sync_runbooks() -> None:
    all_fetched_ids: set[ConfluencePageId] = set()
    folders = confluence_service.get_page_children_pages(
        confluence_service.RUNBOOKS_FOLDER_ID
    )

    for folder in folders:
        runbooks_pages = confluence_service.get_page_children_pages(folder["id"])
        for page in runbooks_pages:
            data = confluence_service.parse_confluence_page(page)
            page_id = data["page_id"]
            all_fetched_ids.add(page_id)
            data["name"] = data["name"].removesuffix("[RUNBOOK]").strip()

            data_editable = cast("dict[str, str]", data)
            data_editable["title"] = (
                data_editable["name"].removesuffix("[RUNBOOK]").strip()
            )
            # Remove everything between braces
            cleaned_title = re.sub(r"\[[^\]]+\]", "", data_editable["title"])
            data_editable["service_type"] = cleaned_title.split(".", maxsplit=1)[
                0
            ].strip()
            data_editable["service_name"] = (
                cleaned_title.split(".", maxsplit=1)[1]
                if "." in cleaned_title
                else cleaned_title
            )

            if data_editable["service_type"] not in ALLOWED_TYPES:
                data_editable["service_type"] = "other"
            try:
                Runbook.objects.update_or_create(
                    page_id=int(data_editable.pop("page_id")), defaults=data_editable
                )
            except IntegrityError:
                logger.exception(f"IntegrityError for {data} {data}")
    # Print all runbooks that are not in the folder anymore
    missing_runbooks = Runbook.objects.exclude(page_id__in=all_fetched_ids)
    if not missing_runbooks:
        logger.info(f"Synced {len(all_fetched_ids)} runbooks. No runbooks to delete.")
        return
    if len(missing_runbooks) > 4:
        logger.warning(
            f"Too many runbooks not found. FireFighter will not delete them automatically, as it might be an API or implementation error. List: {[f'{x.page_id}/ {x.name}' for x in missing_runbooks]}"
        )
        return
    logger.warning(
        f"Missing runbooks that will be deleted: {[f'{x.page_id}/ {x.name}' for x in missing_runbooks]}"
    )
    # Delete all runbooks that are not in the folders anymore
    missing_runbooks.delete()
    return
