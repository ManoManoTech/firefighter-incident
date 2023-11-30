from __future__ import annotations

import logging

from celery import shared_task

from firefighter.confluence.service import confluence_service
from firefighter.confluence.utils import (
    ConfluencePage,
    ConfluencePageId,
    parse_runbook_title,
)

logger = logging.getLogger(__name__)


@shared_task(name="confluence.sort_runbooks", soft_time_limit=60 * 5, time_limit=60 * 7)
def sort_runbooks(*, dry_run: bool = False) -> None:
    """Sort runbooks in Confluence.

    Args:
        dry_run (bool, optional): Should actions be performed? If True, Confluence will be accessed in read-only mode. Defaults to False.
    """
    logger.info(f"Running in {'dry run' if dry_run else 'real'} mode")

    # 1. Get top level pages
    folders = _get_top_level_pages(confluence_service.RUNBOOKS_FOLDER_ID)

    # 2. Sort runbooks in each folder
    sort_runbooks_in_folders(folders, dry_run=dry_run)


def _get_top_level_pages(
    root_page_id: ConfluencePageId,
) -> list[ConfluencePageId]:
    """Get all top level pages in the runbooks folder."""
    folders: list[ConfluencePageId] = []
    children_pages = confluence_service.get_page_children_pages(root_page_id)

    for page in children_pages:
        title: str = page["title"]
        if "TEMPLATE" in title.upper():
            continue
        folders.append(int(page["id"]))
        logger.debug(f"Found runbook folder {title} with id {page['id']}")

    logger.info(f"Found {len(folders)} runbooks folder ({folders})")
    return folders


def sort_runbooks_in_folders(
    folders: list[ConfluencePageId], *, dry_run: bool = False
) -> None:
    """Sort runbooks in each folder.

    Args:
        folders (list[ConfluencePageId]): List of folders to sort runbooks in.
        dry_run (bool, optional): Do not perform the sort. Defaults to False.
    """
    for folder_page_id in folders:
        # Get children per archive page
        children: list[ConfluencePage] = confluence_service.get_page_children_pages(
            folder_page_id, expand=""
        )

        folder_children: list[tuple[ConfluencePageId, str, ConfluencePage]] = []

        for page in children:
            title: str = page["title"]
            page_id: ConfluencePageId = page["id"]

            runbook_name_clean = parse_runbook_title(title)
            if runbook_name_clean:
                folder_children.append((page_id, runbook_name_clean, page))

        sorted_children = sorted(folder_children, key=lambda x: x[1].lower())
        # Check if already sorted
        if sorted_children == folder_children:
            logger.debug(f"Folder {folder_page_id} is already sorted. Skipping")
            continue
        clean_sorted_children: list[tuple[ConfluencePageId, ConfluencePage]] = [
            (x[0], x[2]) for x in sorted_children
        ]
        logger.info(f"Folder {folder_page_id} is not sorted. Sorting")
        confluence_service.sort_pages(clean_sorted_children, dry_run=dry_run)
