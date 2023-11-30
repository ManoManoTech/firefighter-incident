from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from django.forms import ValidationError
from django.utils import timezone

from firefighter.incidents.views.date_utils import (
    get_bounds_from_calendar_year,
    get_bounds_from_quarter,
    get_bounds_from_week,
    get_bounds_from_year,
    get_current_quarter,
    get_last_quarter,
    parse_date_natural,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


RANGE_REGEX = re.compile(
    r"^(?P<iso_year>[iI])?(?P<year>\d{4})?/?(?:[qQ](?P<quarter>[1-4])|([wW](?P<week>5[0-3]|[1-4]\d|[0-4]?[1-9])))?$"
)


SPECIAL_RANGES = ["current_week", "last_week", "current_quarter", "last_quarter"]


def parse_moment(value: str) -> slice | None:
    """Returns a :class:`slice` with the :func:`slice.start` and :func:`slice.stop` of the given moment.
    If the moment is not a valid moment, returns None.
    If the moment is a point in time, returns a slice with the same start and stop.
    """
    value = value.strip()

    # Quarter/Week relative (current/previous quarter, current/previous week)
    if value in SPECIAL_RANGES:
        now = timezone.localtime(timezone.now())
        returned_range = get_date_range_from_relative_calendar_value(value, now, value)
        if None not in returned_range:
            return slice(returned_range[0], returned_range[1])

    # Match according to the regex (W20, Q4, YYYY-W20, YYYY-Q4...)
    week_or_quarter_time_frame = (*get_date_range_from_calendar_value(value), value)
    if None not in week_or_quarter_time_frame:
        return slice(week_or_quarter_time_frame[0], week_or_quarter_time_frame[1])

    # Match using dateparser (lots of formats)
    return parse_date_natural(value)


def get_date_range_from_special_date(
    unparsed_date: str,
) -> tuple[datetime | None, datetime | None, str | None, str | None]:
    """TODO Specify the year parameter (ISO or calendar)."""
    if "-" in unparsed_date:
        logger.debug("Parsing range, splitting with /")

        if unparsed_date.count("-") == 1:
            split = unparsed_date.split("-")
        elif unparsed_date.count(" - ") == 1:
            split = unparsed_date.split(" - ")
        else:
            err_msg = f"Invalid range: {unparsed_date}. Only one separator is allowed"
            raise ValidationError(err_msg)
        if len(split) == 2:
            for i in range(2):
                split[i] = split[i].strip()

            beg = parse_moment(split[0])
            end = parse_moment(split[1])
            logger.debug(end)
            return (
                beg.start if beg else None,
                end.stop if end else None,
                None,
                split[0] + "-" + split[1],
            )
        # TODO Message warning + logger.warning
        raise ValidationError(
            "Invalid range: %(unparsed_date)s. Only one separator is allowed",
            params={"unparsed_date": unparsed_date},
            code="invalid",
        )
    try:
        date_range = parse_moment(unparsed_date)
    except ValueError as exc:
        raise ValidationError(
            "Invalid range: %(unparsed_date)s. %(error)s",
            params={"unparsed_date": unparsed_date, "error": str(exc)},
            code="invalid",
        ) from exc
    if date_range:
        return date_range.start, date_range.stop, None, "TODO"

    # TODO Message warning + logger.warning
    return None, None, None, None


def get_date_range_from_relative_calendar_value(
    unparsed_date: str, now: datetime, date_input: str
) -> tuple[datetime, datetime, str, str] | tuple[None, None, None, None]:
    if unparsed_date == "current_week":
        year, week, _weekday = now.date().isocalendar()
        return *get_bounds_from_week(year, week), date_input
    if unparsed_date == "last_week":
        year, week, _weekday = (now.date() + relativedelta(days=-7)).isocalendar()
        return *get_bounds_from_week(year, week), date_input
    if unparsed_date == "current_quarter":
        quarter_year, quarter_number = get_current_quarter()
        return *get_bounds_from_quarter(quarter_year, quarter_number), date_input
    if unparsed_date == "last_quarter":
        quarter_year, quarter_number = get_last_quarter()
        return *get_bounds_from_quarter(quarter_year, quarter_number), date_input
    return None, None, None, None


def get_date_range_from_calendar_value(
    date_range: str,
) -> tuple[datetime | None, datetime | None, str | None]:
    match = RANGE_REGEX.match(date_range)

    if not match:
        return None, None, None

    dict_match = match.groupdict()

    year = (
        int(dict_match["year"])
        if dict_match.get("year")
        else timezone.localtime(timezone.now()).date().year
    )

    if dict_match.get("quarter"):
        return get_bounds_from_quarter(year, int(dict_match["quarter"]))
    if dict_match.get("week"):
        return get_bounds_from_week(year, int(dict_match["week"]))
    if dict_match.get("year"):
        if dict_match.get("iso_year"):
            return get_bounds_from_year(year)
        return get_bounds_from_calendar_year(year)

    return None, None, None


def get_range_look_args(
    gte: datetime | None, lte: datetime | None, field_name: str
) -> dict[str, datetime]:
    if gte and lte:
        return {
            f"{field_name}__gte": gte,
            f"{field_name}__lte": lte,
        }
    if lte:
        return {f"{field_name}__lte": lte}
    if gte:
        return {
            f"{field_name}__gte": gte,
        }
    return {}
