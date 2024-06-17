from __future__ import annotations

import logging
import operator

from celery import shared_task
from django.utils.timezone import (  # type: ignore[attr-defined]
    datetime,
    get_current_timezone,
    timedelta,
)

from firefighter.confluence.service import confluence_service
from firefighter.confluence.utils import (
    CONFLUENCE_PM_ARCHIVE_TITLE_REGEX,
    CONFLUENCE_PM_TITLE_REGEX,
    ConfluencePage,
    ConfluencePageId,
    parse_postmortem_title,
)
from firefighter.firefighter.utils import get_in
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.views.date_utils import get_quarter_from_week

logger = logging.getLogger(__name__)


@shared_task(
    name="confluence.archive_and_sort_postmortems",
    soft_time_limit=60 * 5,
    time_limit=60 * 7,
)
def archive_and_sort_postmortems(*, dry_run: bool = True) -> None:
    """Archive postmortems that are older than 2 weeks, for incidents that are closed.

    Args:
        dry_run (bool, optional): Should actions be performed? If True, Confluence will be accessed in read-only mode. Defaults to False.
    """
    logger.info(f"Running in {'dry run' if dry_run else 'real'} mode")

    # 1. Get top level pages
    pm_to_sort, quarter_bins = _get_top_level_pages(
        confluence_service.POSTMORTEM_FOLDER_ID
    )

    # 2. Create current quarter folder if it does not exist
    create_current_bin_if_needed(quarter_bins, dry_run=dry_run)

    # 3. Archive postmortems in root into their quarter folder (if appropriate)
    _archive_postmortems(pm_to_sort, quarter_bins, dry_run=dry_run)

    # 4. Move archived postmortems in the right quarter folder if there is any error
    # Not needed atm

    # 5. Sort postmortems in each quarter folder
    sort_postmortems_in_bins(quarter_bins, dry_run=dry_run)


def _get_top_level_pages(
    root_page_id: ConfluencePageId,
) -> tuple[list[ConfluencePage], dict[str, int]]:
    """Get all top level pages in the postmortem folder."""
    pm_to_sort: list[ConfluencePage] = []
    quarter_bins: dict[str, int] = {}
    children_pages = confluence_service.get_page_children_pages(root_page_id)

    for page in children_pages:
        title: str = page["title"]
        page_id: int = int(page["id"])

        pm_reg = CONFLUENCE_PM_TITLE_REGEX.match(title)
        if pm_reg:
            pm_to_sort.append(page)
            continue

        quarter_bin = CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.search(title)
        if not quarter_bin:
            if "[Template]" not in title:
                logger.warning(f"Could not match `{title}`, ID: {page_id}")
            continue
        year = quarter_bin.group(2)
        quarter = quarter_bin.group(1)
        fmt = f"{year}Q{quarter}"
        if fmt in quarter_bins:
            logger.warning(f"Found duplicate quarter bin: {fmt}")
        quarter_bins[fmt] = page_id
        logger.debug(f"Found quarter {fmt} with id {page_id}")

    logger.info(f"Found {len(pm_to_sort)} postmortems to sort in root folder.")
    logger.info(f"Found {len(quarter_bins)} quarters bins ({quarter_bins})")
    return pm_to_sort, quarter_bins


def _archive_postmortems(
    pm_to_sort: list[ConfluencePage],
    quarter_bins: dict[str, int],
    *,
    dry_run: bool = False,
) -> None:
    """Move postmortems to their quarter bin, if they have a related incident in FireFighter that is closed for more than 7 days.

    Args:
        pm_to_sort (list[ConfluencePage]): Confluence pages to sort. Not Django models, but the JSON response from the API.
        quarter_bins (dict[str, int]): Mapping of quarter/year to Confluence page ID.
        dry_run (bool, optional): Defaults to False.
    """
    for pm in pm_to_sort:
        if not pm["title"].startswith("#"):
            logger.debug(f"Skipping {pm['title']} because it does not look like a PM")
            continue

        date_, fmt = parse_postmortem_title(pm["title"])
        if not date_ or not fmt:
            logger.error(f"Could not parse {pm['title']} from page id {pm['id']}")
            continue
        if fmt not in quarter_bins:
            logger.error(f"Could not find quarter page {fmt} for {pm['title']}")
            continue

        incident = Incident.objects.filter(postmortem_for__page_id=pm["id"]).first()
        if not incident:
            logger.warning(
                f"Could not find incident for `{pm['title']}` ({pm['id']}). Is it linked in FireFighter and has it the correct title format?"
            )
            continue
        if incident.status != IncidentStatus.CLOSED:
            logger.debug(f"Skipping `{pm['title']}` because incident is not closed")
            continue
        latest_closed_status = (
            incident.incidentupdate_set.filter(_status=IncidentStatus.CLOSED)
            .order_by("-created_at")
            .first()
        )
        if not latest_closed_status:
            logger.warning(
                f"Could not find latest closed status for incident #{incident.id}."
            )
            continue
        if latest_closed_status.created_at >= datetime.now(
            tz=get_current_timezone()
        ) - timedelta(days=7):
            logger.debug(
                f"Skipping `{pm['title']}` because incident is not closed for more than 7 days"
            )
            continue

        confluence_service.move_page(pm["id"], quarter_bins[fmt], dry_run=dry_run)


def create_current_bin_if_needed(
    quarter_bins: dict[str, int], *, dry_run: bool = False
) -> bool:
    current_quarter = get_quarter_from_week(datetime.now().isocalendar()[1])
    current_year = datetime.now().isocalendar()[0]
    current_quarter_year = f"{current_year}Q{current_quarter}"
    if current_quarter_year not in quarter_bins:
        page_id = create_current_bin(
            quarter_bins, current_quarter, current_year, dry_run=dry_run
        )
        quarter_bins[current_quarter_year] = page_id
        return True
    return False


def create_current_bin(
    quarter_bins: dict[str, int],
    current_quarter: int,
    current_year: int,
    *,
    dry_run: bool = False,
) -> int:
    res = confluence_service.create_page(
        f"Q{current_quarter} {current_year} Postmortems",
        confluence_service.POSTMORTEM_FOLDER_ID,
        body="",
    )
    page_id = int(get_in(res, "id"))
    confluence_service.move_page(
        page_id,
        next(iter(quarter_bins.keys())),
        position="before",
        dry_run=dry_run,
    )

    return page_id


def sort_postmortems_in_bins(
    quarter_bins: dict[str, int], *, dry_run: bool = False
) -> None:
    """Sort postmortems in each quarter archive folder.

    Args:
        quarter_bins (dict[str, int]): _description_
        dry_run (bool, optional): _description_. Defaults to False.
    """
    for quarter, quarter_page_id in quarter_bins.items():
        # Get children per archive page
        children: list[ConfluencePage] = confluence_service.get_page_children_pages(
            quarter_page_id, expand=""
        )
        logger.info(f"Found {len(children)} postmortems in {quarter}")
        quarter_children: list[tuple[int, datetime, ConfluencePage]] = []

        for page in children:
            title: str = page["title"]
            page_id: int = int(page["id"])

            date_, fmt = parse_postmortem_title(title)
            if date_ and fmt:
                quarter_children.append((page_id, date_, page))

        sorted_children = sorted(quarter_children, key=operator.itemgetter(1), reverse=True)
        # Check if already sorted
        if sorted_children == quarter_children:
            logger.debug(f"Quarter {quarter} is already sorted. Skipping")
            continue

        logger.info(f"Quarter {quarter} is not sorted. Sorting")

        clean_sorted: list[tuple[ConfluencePageId, ConfluencePage]] = [
            (x[0], x[2]) for x in sorted_children
        ]

        confluence_service.sort_pages(clean_sorted, dry_run=dry_run)

        logger.info(f"Fetched {len(quarter_children)} postmortems")
