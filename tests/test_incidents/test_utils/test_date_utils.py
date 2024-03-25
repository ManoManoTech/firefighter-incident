from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from firefighter.incidents.views.date_filter import (
    get_date_range_from_calendar_value,
    get_date_range_from_special_date,
    get_range_look_args,
    parse_date_natural,
)
from firefighter.incidents.views.date_utils import (
    TZ,
    get_bounds_from_quarter,
    get_bounds_from_week,
    make_bounds_timezone_aware,
)

logger = logging.getLogger(__name__)


# @pytest.mark.django_db()
def test_get_date_from_quarter() -> None:
    # From Monday 3rd Jan to Sun 3rd Apr (included)
    assert get_bounds_from_quarter(2022, 1) == (
        datetime(2022, 1, 3, 0, 0, tzinfo=TZ),
        datetime(2022, 4, 3, 23, 59, 59, 999999, tzinfo=TZ),
        "2022-Q1",
    )

    assert get_bounds_from_quarter(2023, 4) == (
        datetime(2023, 10, 2, 0, 0, tzinfo=TZ),
        datetime(2023, 12, 31, 23, 59, 59, 999999, tzinfo=TZ),
        "2023-Q4",
    )


def test_get_date_from_week() -> None:
    assert get_bounds_from_week(2022, 1) == (
        datetime(2022, 1, 3, 0, 0, tzinfo=TZ),
        datetime(2022, 1, 9, 23, 59, 59, 999999, tzinfo=TZ),
        "2022-W1",
    )
    assert get_bounds_from_week(2022, 2) == (
        datetime(2022, 1, 10, 0, 0, tzinfo=TZ),
        datetime(2022, 1, 16, 23, 59, 59, 999999, tzinfo=TZ),
        "2022-W2",
    )
    assert get_bounds_from_week(2022, 52) == (
        datetime(2022, 12, 26, 0, 0, tzinfo=TZ),
        datetime(2023, 1, 1, 23, 59, 59, 999999, tzinfo=TZ),
        "2022-W52",
    )


def test_bounds_dateparser() -> None:
    date_slice = parse_date_natural("May 2022")
    assert date_slice is not None
    assert date_slice.start == datetime(2022, 5, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(2022, 5, 31, 23, 59, 59, 999999, tzinfo=TZ)

    date_slice = parse_date_natural("1 may 2022")
    assert date_slice is not None
    assert date_slice.start == datetime(2022, 5, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(2022, 5, 1, 23, 59, 59, 999999, tzinfo=TZ)

    date_slice = parse_date_natural("may 1")
    assert date_slice is not None
    assert date_slice.start == datetime(datetime.now().year, 5, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(
        datetime.now().year, 5, 1, 23, 59, 59, 999999, tzinfo=TZ
    )

    date_slice = parse_date_natural("1 may")
    assert date_slice is not None
    assert date_slice.start == datetime(datetime.now().year, 5, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(
        datetime.now().year, 5, 1, 23, 59, 59, 999999, tzinfo=TZ
    )

    date_slice = parse_date_natural("1 jan")
    assert date_slice is not None
    assert date_slice.start == datetime(datetime.now().year, 1, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(
        datetime.now().year, 1, 1, 23, 59, 59, 999999, tzinfo=TZ
    )

    date_slice = parse_date_natural("jan 1")
    assert date_slice is not None
    assert date_slice.start == datetime(datetime.now().year, 1, 1, 0, 0, tzinfo=TZ)
    assert date_slice.stop == datetime(
        datetime.now().year, 1, 1, 23, 59, 59, 999999, tzinfo=TZ
    )


# Move to test parser TODO


def test_parse_date_frame() -> None:
    date_range = get_date_range_from_special_date("2022/Q1")
    beg, end = make_bounds_timezone_aware(
        datetime(2022, 1, 3, 0, 0),  # noqa: DTZ001
        datetime(2022, 4, 3, 23, 59, 59, 999999),  # noqa: DTZ001
    )
    assert date_range[0] == beg
    assert date_range[1] == end


def test_parse_date_frame_2() -> None:
    date_range = get_date_range_from_special_date("2022/Q1 - 2022/Q2")
    beg, end = make_bounds_timezone_aware(
        datetime(2022, 1, 3, 0, 0),  # noqa: DTZ001
        datetime(2022, 7, 3, 23, 59, 59, 999999),  # noqa: DTZ001
    )
    assert date_range[0] == beg
    assert date_range[1] == end


def test_parse_date_frame_3() -> None:
    date_range = get_date_range_from_special_date("2022/Q1 - May 2022")
    beg, end = (
        datetime(2022, 1, 3, 0, 0, tzinfo=TZ),
        datetime(2022, 5, 31, 23, 59, 59, 999999, tzinfo=TZ),
    )

    assert date_range[0] == beg
    assert date_range[1] == end


@pytest.mark.parametrize(
    ("gte", "lte", "field_name", "expected"),
    [
        (
            datetime(year=2023, month=1, day=1, tzinfo=UTC),
            datetime(year=2023, month=1, day=20, tzinfo=UTC),
            "field",
            {
                "field__gte": datetime(year=2023, month=1, day=1, tzinfo=UTC),
                "field__lte": datetime(year=2023, month=1, day=20, tzinfo=UTC),
            },
        ),
        (
            datetime(year=2023, month=1, day=1, tzinfo=UTC),
            None,
            "field",
            {"field__gte": datetime(year=2023, month=1, day=1, tzinfo=UTC)},
        ),
        (
            None,
            datetime(year=2023, month=1, day=20, tzinfo=UTC),
            "field",
            {"field__lte": datetime(year=2023, month=1, day=20, tzinfo=UTC)},
        ),
        (None, None, "field", {}),
    ],
)
def test_get_range_look_args(gte, lte, field_name, expected):
    result = get_range_look_args(gte, lte, field_name)
    assert result == expected


@pytest.mark.parametrize(
    ("date_range", "expected"),
    [
        (
            "2022",
            (
                datetime(year=2022, month=1, day=1, tzinfo=TZ),
                datetime(year=2023, month=1, day=1, tzinfo=TZ)
                - timedelta(microseconds=1),
                "2022",
            ),
        ),
        (
            "I2022",
            (
                datetime(year=2022, month=1, day=3, tzinfo=TZ),
                datetime(year=2023, month=1, day=2, tzinfo=TZ)
                - timedelta(microseconds=1),
                "ISO2022",
            ),
        ),
        (
            "2021/Q4",
            (
                datetime(year=2021, month=10, day=4, tzinfo=TZ),
                datetime(year=2022, month=1, day=3, tzinfo=TZ)
                - timedelta(microseconds=1),
                "2021-Q4",
            ),
        ),
        (
            "2022/W20",
            (
                datetime(year=2022, month=5, day=16, tzinfo=TZ),
                datetime(year=2022, month=5, day=23, tzinfo=TZ)
                - timedelta(microseconds=1),
                "2022-W20",
            ),
        ),
        ("invalid_input", (None, None, None)),
    ],
)
def test_get_date_range_from_calendar_value(date_range, expected):
    result = get_date_range_from_calendar_value(date_range)
    assert result == expected
