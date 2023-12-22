from __future__ import annotations

import operator
from datetime import UTC, datetime, timedelta

from django_htmx.middleware import HtmxDetails

from firefighter.firefighter.filters import (
    apply_filter,
    get_item,
    readable_time_delta,
    timedelta_chop_microseconds,
)
from firefighter.firefighter.utils import (
    AuthenticatedHttpRequest,
    HtmxHttpRequest,
    get_first_in,
    get_in,
    is_during_office_hours,
)
from firefighter.incidents.models.user import User


def test_get_in() -> None:
    sample_dict = {"a": {"b": {"c": 42}}}
    assert get_in(sample_dict, "a.b.c") == 42
    assert get_in(sample_dict, ["a", "b", "c"]) == 42
    assert get_in(sample_dict, "a.b.d", default=0) == 0
    assert get_in(None, "a.b.c", default=0) is None
    assert get_in(sample_dict, "", default=0) == 0
    assert get_in(sample_dict, []) == sample_dict


def test_get_first_in() -> None:
    sample_list = [{"a": 1}, {"a": 2}, {"a": 3}]
    assert get_first_in(sample_list, "a", [2, 3]) == {"a": 2}
    assert get_first_in(sample_list, "a", [4, 5], default={"a": 4}) == {"a": 4}
    assert get_first_in(None, "a", [1, 2], default={"a": 0}) == {"a": 0}
    assert get_first_in([], "a", [1, 2], default={"a": 0}) == {"a": 0}


def test_timedelta_chop_microseconds() -> None:
    delta = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=123456)
    chopped = timedelta(days=1, hours=2, minutes=3, seconds=4)
    assert timedelta_chop_microseconds(delta) == chopped


def test_get_item() -> None:
    sample_dict = {"a": 1, "b": 2, "c": 3}
    assert get_item(sample_dict, "a") == 1
    assert get_item(sample_dict, "d") is None

    class TestClass:
        def __init__(self):
            self.a = 1
            self.b = 2

        def __getitem__(self, key):
            if key == "c":
                return 3
            raise KeyError(key)

    obj = TestClass()
    assert get_item(obj, "a") == 1
    assert get_item(obj, "b") == 2
    assert get_item(obj, "c") == 3
    assert get_item(obj, "d") is None
    assert get_item(obj, "__class__") == TestClass


def test_apply_filter() -> None:
    fn_holder = {"filter": operator.mul, "filter_args": 2}
    assert apply_filter(5, fn_holder) == 10

    fn_holder = {"filter": lambda x: x * 2}
    assert apply_filter(5, fn_holder) == 10

    assert apply_filter(5, {}) == 5


def test_readable_time_delta() -> None:
    delta = timedelta(hours=2, minutes=3, seconds=4)
    assert readable_time_delta(delta) == "2 hours and 3 minutes"

    delta = timedelta(days=7, hours=2, minutes=3, seconds=4)
    assert readable_time_delta(delta) == "1 week"

    delta = timedelta(seconds=54)
    assert readable_time_delta(delta) == "an instant"

    delta = timedelta(days=1, hours=2, minutes=3, seconds=4)
    assert readable_time_delta(delta) == "1 day"

    delta = timedelta(days=-1, hours=-2, minutes=-3, seconds=-4)
    assert readable_time_delta(delta) == "-1 day"


def test_is_during_office_hours() -> None:
    dt = datetime(2021, 9, 1, 9, 30, tzinfo=UTC)  # Wednesday, 9:30 AM
    assert is_during_office_hours(dt) is True

    dt = datetime(2021, 9, 1, 18, 30, tzinfo=UTC)  # Wednesday, 6:30 PM
    assert is_during_office_hours(dt) is False


def test_htmx_http_request() -> None:
    htmx_details = HtmxDetails("test")
    request = HtmxHttpRequest()
    request.htmx = htmx_details
    assert request.htmx == htmx_details


def test_authenticated_http_request() -> None:
    user = User(username="testuser")
    request = AuthenticatedHttpRequest()
    request.user = user
    assert request.user == user
