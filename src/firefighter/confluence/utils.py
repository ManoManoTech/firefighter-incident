from __future__ import annotations

import re
from typing import TypeAlias, TypedDict

from django.utils.timezone import (  # type: ignore[attr-defined]
    datetime,
    get_current_timezone,
)

from firefighter.incidents.views.date_utils import get_quarter_from_week

ConfluencePageId: TypeAlias = int | str
"""Alias of `int | str`"""


class ConfluenceContentVersionData(TypedDict, total=False):
    when: datetime | None
    friendlyWhen: str | None
    message: str | None
    number: int | None
    minorEdit: bool | None
    syncRev: str | None
    syncRevSource: str | None
    confRev: str | None
    contentTypeModified: bool | None


class ConfluenceContentLinksData(TypedDict, total=False):
    self: str
    tinyui: str | None
    editui: str | None
    webui: str | None


class ConfluencePage(TypedDict):
    id: ConfluencePageId
    type: str
    status: str | None
    title: str
    version: ConfluenceContentVersionData | None
    links: ConfluenceContentLinksData | None
    body: dict[str, str] | None


class PageInfo(TypedDict):
    """Dict mapped to mandatory fields for a [firefighter.confluence.models.ConfluencePage][]."""

    name: str
    page_id: str
    page_url: str
    page_edit_url: str


CONFLUENCE_TITLE = r"\#(?P<date>\d{8}-inc|\d{8})-(?P<id>\d{2,4})(-[a-zA-Z0-9-]+( |$)| )(?P<priority>\((?:(SEV|P)-?\s?[1-5]{1}\))|(?:\(GAMEDAY\)))?[ \t]?(?P<title>.*)?"
CONFLUENCE_PM_TITLE_REGEX = re.compile(CONFLUENCE_TITLE)

CONFLUENCE_PM_ARCHIVE_TITLE = r"^(?:\[Archive\] )?Q([1-4]) (\d{4})"
CONFLUENCE_PM_ARCHIVE_TITLE_REGEX = re.compile(CONFLUENCE_PM_ARCHIVE_TITLE)


def parse_postmortem_title(title: str) -> tuple[datetime, str] | tuple[None, None]:
    """Parse postmortem title and return the date and quarter associated to this date, in the format YYYYQX.

    Args:
        title (str): Title of the postmortem, in the format #YYYYMMDD-<id>-<component> (SEV/P<N>) <title>

    Returns:
        tuple[datetime, str] | tuple[None, None]: Date and quarter associated to this date.
    """
    match = CONFLUENCE_PM_TITLE_REGEX.match(title)
    if not match:
        return None, None

    res = match.groupdict()
    grp = res["date"]
    grp = grp.replace("-inc", "")

    date_ = datetime.strptime(grp, "%Y%m%d").replace(tzinfo=get_current_timezone())
    quarter = get_quarter_from_week(date_.isocalendar()[1])
    year = date_.isocalendar()[0]
    fmt = f"{year}Q{quarter}"
    return date_, fmt


def parse_postmortem_archive_title(title: str) -> re.Match[str] | None:
    return CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.match(title)


def parse_runbook_title(title: str) -> str | None:
    """Parse runbooks title and return the service name, or None if the title is not valid.

    Useful to remove prefixes like [WIP] or [ARCHIVED] from the title, to sort runbooks.

    Args:
        title (str): Title of the runbook

    Returns:
        str | None: Service name or None if the title is not valid.
    """
    if "[RUNBOOK]" not in title or "[TEMPLATE]" in title.upper():
        return None

    # Remove leading text in brackets
    title = re.sub(r"^\[.*\] ", "", title)
    return title.strip()
