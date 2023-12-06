from __future__ import annotations

import functools
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import BadRequest
from django.utils import timezone

if TYPE_CHECKING:
    from dateparser.date import DateDataParser

TZ = timezone.get_current_timezone()


@functools.cache
def get_ddp() -> DateDataParser:
    # ruff: noqa: PLC0415
    from dateparser.date import DateDataParser

    return DateDataParser(
        locales=["en"],
        settings={
            "RETURN_TIME_AS_PERIOD": True,
            "DATE_ORDER": "YMD",
            "TIMEZONE": settings.TIME_ZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )


def get_current_quarter() -> tuple[int, int]:
    year, week, _weekday = (timezone.localtime(timezone.now()).date()).isocalendar()
    current_week_monday = date.fromisocalendar(year=year, week=week, day=1)
    current_week_year, current_week_number, _ = current_week_monday.isocalendar()
    current_quarter = get_quarter_from_week(current_week_number)
    return current_week_year, current_quarter


def get_last_quarter() -> tuple[int, int]:
    current_year, current_quarter = get_current_quarter()
    if current_quarter == 1:
        return current_year - 1, 4
    return current_year, current_quarter - 1


def get_quarter_from_week(week_number: str | int) -> int:
    week_number = int(week_number)
    if 0 < week_number <= 13:
        return 1
    if 13 < week_number <= 26:
        return 2
    if 26 < week_number <= 39:
        return 3
    if 39 < week_number <= 53:
        return 4
    raise BadRequest("Invalid week number.")


def get_bounds_from_calendar_year(year_value: int) -> tuple[datetime, datetime, str]:
    """Calendar Year."""
    lower_bound = datetime(year_value, 1, 1, tzinfo=TZ)
    upper_bound = datetime(year_value, 12, 31, 23, 59, 59, 999999, tzinfo=TZ)

    return (
        lower_bound,
        upper_bound,
        f"{year_value}",
    )


def get_bounds_from_year(year_value: int) -> tuple[datetime, datetime, str]:
    """ISO Year."""
    lower_bound = datetime.fromisocalendar(year_value, 1, 1)
    upper_week_nb = date(year_value, 12, 28).isocalendar()[1]
    upper_bound = datetime.combine(
        date.fromisocalendar(year=year_value, week=upper_week_nb, day=7),
        time(23, 59, 59, 999999),
    )

    return *make_bounds_timezone_aware(lower_bound, upper_bound), f"ISO{year_value}"


def get_bounds_from_week(
    year_value: int, week_value: int
) -> tuple[datetime, datetime, str]:
    lower_bound = datetime.fromisocalendar(year_value, week_value, 1).astimezone(TZ)
    upper_bound = datetime.combine(
        date.fromisocalendar(year_value, week_value, 7),
        time(23, 59, 59, 999999),
        tzinfo=TZ,
    )

    return lower_bound, upper_bound, f"{year_value}-W{week_value}"


def get_bounds_from_quarter(
    year_nb: int, quarter_nb: int
) -> tuple[datetime, datetime, str]:
    lower_week_nb = quarter_nb * 13 - 12
    lower_bound = datetime.fromisocalendar(year_nb, lower_week_nb, 1)
    if quarter_nb != 4:
        upper_bound = datetime.fromisocalendar(
            year_nb, lower_week_nb + 13, 1
        ) - timedelta(microseconds=1)
    else:
        # The last week of ISO year always contains the 28th december. It can be W52 or W53.
        upper_week_nb = date(year_nb, 12, 28).isocalendar()[1]
        upper_bound = datetime.combine(
            date.fromisocalendar(year=year_nb, week=upper_week_nb, day=7),
            time(23, 59, 59, 999999),
        )

    return (
        *make_bounds_timezone_aware(lower_bound, upper_bound),
        f"{year_nb}-Q{quarter_nb}",
    )


def get_day_date_range(date_: date) -> slice:
    return slice(
        datetime(date_.year, date_.month, date_.day, 0, 0, 0, tzinfo=TZ),
        datetime(date_.year, date_.month, date_.day, 23, 59, 59, 999999, tzinfo=TZ),
    )


def get_month_date_range(date_: date) -> slice:
    return slice(
        datetime(date_.year, date_.month, 1, 0, 0, 0, tzinfo=TZ),
        datetime(
            date_.year,
            date_.month,
            monthrange(date_.year, date_.month)[1],
            23,
            59,
            59,
            999999,
            tzinfo=TZ,
        ),
    )


def make_bounds_timezone_aware(
    lower_bound: datetime, upper_bound: datetime
) -> tuple[datetime, datetime]:
    if settings.USE_TZ:
        tz = timezone.get_current_timezone()
        lower_bound = timezone.make_aware(lower_bound, tz)
        upper_bound = timezone.make_aware(upper_bound, tz)
    return lower_bound, upper_bound


def make_timezone_aware(lower_bound: datetime) -> datetime:
    if settings.USE_TZ:
        tz = timezone.get_current_timezone()
        lower_bound = timezone.make_aware(lower_bound, tz)
    return lower_bound


def get_biggest_date(a: datetime | None, b: datetime) -> datetime:
    if not a:
        return b
    if not b:
        return a
    if a < b:
        return b
    return a


def parse_date_natural(value: str) -> slice | None:
    # TODO Reuse the DateDataParser and tune the config

    date_date = get_ddp().get_date_data(value)
    if date_date.date_obj:
        date_ = date_date.date_obj
        if date_date.period == "month":
            return get_month_date_range(date_)
        if date_date.period == "day":
            return get_day_date_range(date_)
        if date_date.period == "year":
            a = get_bounds_from_year(date_.year)
            return slice(a[0], a[1])
        if date_date.period == "week":
            a = get_bounds_from_week(date_.year, date_.isocalendar()[1])
            return slice(a[0], a[1])
        return slice(date_, date_)
    return None
