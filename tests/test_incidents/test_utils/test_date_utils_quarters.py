"""Tests for the quarter helpers, get_biggest_date and the remaining parse_date_natural periods."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import BadRequest

from firefighter.incidents.views.date_utils import (
    TZ,
    get_biggest_date,
    get_current_quarter,
    get_last_quarter,
    get_quarter_from_week,
    parse_date_natural,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("week", "quarter"),
    [(1, 1), ("13", 1), (14, 2), (26, 2), (27, 3), (39, 3), (40, 4), (53, 4)],
)
def test_get_quarter_from_week(week: int | str, quarter: int) -> None:
    assert get_quarter_from_week(week) == quarter


@pytest.mark.parametrize("week", [0, 54, -1])
def test_get_quarter_from_week_rejects_invalid_week(week: int) -> None:
    with pytest.raises(BadRequest, match="Invalid week number"):
        get_quarter_from_week(week)


def _freeze_now(mocker: MockerFixture, now: datetime) -> None:
    mocker.patch(
        "firefighter.incidents.views.date_utils.timezone.now", return_value=now
    )


def test_get_current_quarter_uses_the_iso_year_of_the_current_week(
    mocker: MockerFixture,
) -> None:
    # Friday 2021-01-01 belongs to ISO week 53 of 2020, so to Q4 2020
    _freeze_now(mocker, datetime(2021, 1, 1, 12, tzinfo=UTC))

    assert get_current_quarter() == (2020, 4)


def test_get_current_quarter_mid_year(mocker: MockerFixture) -> None:
    _freeze_now(mocker, datetime(2022, 5, 18, 12, tzinfo=UTC))

    assert get_current_quarter() == (2022, 2)


def test_get_last_quarter_in_the_same_year(mocker: MockerFixture) -> None:
    _freeze_now(mocker, datetime(2022, 5, 18, 12, tzinfo=UTC))

    assert get_last_quarter() == (2022, 1)


def test_get_last_quarter_wraps_to_the_previous_year(mocker: MockerFixture) -> None:
    _freeze_now(mocker, datetime(2022, 2, 16, 12, tzinfo=UTC))

    assert get_last_quarter() == (2021, 4)


class TestGetBiggestDate:
    earlier = datetime(2022, 1, 1, tzinfo=UTC)
    later = datetime(2022, 6, 1, tzinfo=UTC)

    def test_missing_first_date_returns_the_second(self) -> None:
        assert get_biggest_date(None, self.later) == self.later

    def test_returns_the_later_date_whatever_the_order(self) -> None:
        assert get_biggest_date(self.earlier, self.later) == self.later
        assert get_biggest_date(self.later, self.earlier) == self.later


class TestParseDateNaturalPeriods:
    @staticmethod
    def test_year_spans_its_iso_weeks() -> None:
        date_slice = parse_date_natural("2022")

        assert date_slice is not None
        assert date_slice.start == datetime(2022, 1, 3, tzinfo=TZ)
        assert date_slice.stop == datetime(2023, 1, 1, 23, 59, 59, 999999, tzinfo=TZ)

    @staticmethod
    def test_week_spans_monday_to_sunday() -> None:
        date_slice = parse_date_natural("last week")

        assert date_slice is not None
        assert date_slice.start.weekday() == 0
        assert date_slice.stop - date_slice.start == timedelta(
            days=6, hours=23, minutes=59, seconds=59, microseconds=999999
        )

    @staticmethod
    def test_exact_time_is_a_single_instant() -> None:
        date_slice = parse_date_natural("2022-03-04 10:30")

        assert date_slice is not None
        assert date_slice.start == date_slice.stop
        assert (date_slice.start.date().isoformat(), date_slice.start.hour) == (
            "2022-03-04",
            10,
        )

    @staticmethod
    def test_unparsable_value_returns_none() -> None:
        assert parse_date_natural("gibberish xyz") is None
