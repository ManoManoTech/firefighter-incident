from __future__ import annotations

import logging
from typing import cast

from celery import shared_task
from django.db.utils import IntegrityError

from firefighter.confluence.models import PostMortem
from firefighter.confluence.service import confluence_service
from firefighter.confluence.utils import (
    CONFLUENCE_PM_TITLE_REGEX,
    parse_postmortem_archive_title,
)
from firefighter.incidents.models.incident import Incident

logger = logging.getLogger(__name__)


@shared_task(name="confluence.sync_postmortems")
def sync_postmortems() -> None:
    all_pm = confluence_service.get_page_descendant_pages(
        confluence_service.POSTMORTEM_FOLDER_ID
    )
    pm_missing_incident = []
    pm_no_match = []

    for pm in all_pm:
        data = confluence_service.parse_confluence_page(pm)

        if "name" not in data or data["name"] is None or data["name"] == "":
            logger.error(f"PostMortem {pm['id']} has no name")
            continue

        # Ignore [ARCHIVE] folders
        if parse_postmortem_archive_title(data["name"]) is not None:
            continue

        # Ignore any template page
        if "[TEMPLATE]" in data["name"].upper():
            continue

        # Ignore any page whose title does not start with a #
        if not data["name"].startswith("#"):
            continue

        match = CONFLUENCE_PM_TITLE_REGEX.match(data["name"])
        if not match:
            pm_no_match.append(data["name"])
            continue

        match_dict = match.groupdict()
        incident_id = match_dict.get("id")
        if not incident_id:
            continue
        if not Incident.objects.filter(id=incident_id).exists():
            pm_missing_incident.append(data["name"])
            continue
        data_editable = cast("dict[str, str]", data)
        try:
            PostMortem.objects.update_or_create(
                page_id=int(data_editable.pop("page_id")),
                defaults=data_editable
                | {
                    "incident_id": incident_id,
                },
            )
        except IntegrityError:
            logger.exception(f"IntegrityError for {data} {pm}")
    logger.info(pm_missing_incident)
    logger.info(pm_no_match)
