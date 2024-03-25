from __future__ import annotations

import logging
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from django.conf import settings
from django.http import HttpRequest

from firefighter.incidents.enums import IncidentStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import datetime

    from django_htmx.middleware import HtmxDetails

    from firefighter.incidents.models.user import User


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=dict[str, Any])
V = TypeVar("V")


def get_in(
    dictionary: dict[str, Any] | Any | None,
    keys: str | Sequence[str],
    default: Any | None = None,
) -> Any:
    """Get a value from arbitrarily nested dicts."""
    if dictionary is None:
        return None

    if isinstance(keys, str):
        keys = keys.split(".")
    if not keys:
        return dictionary
    if len(keys) == 1:
        return dictionary.get(keys[0], default)
    return get_in(dictionary.get(keys[0], {}), keys[1:], default=default)


def get_first_in(
    ulist: list[T],
    key: str | Sequence[str],
    matches: Iterable[str],
    default: V | None = None,
) -> T | V | None:
    """Returns the first element of a list of dicts, where the value of a key matches one in the provided iterable."""
    if not isinstance(ulist, list) or ulist is None:
        return default  # type: ignore[unreachable]
    return next(
        (e for e in ulist if get_in(e, key) in matches),
        default,
    )


def get_global_context(request: HttpRequest) -> dict[str, str | int | Any]:
    return {
        "APP_DISPLAY_NAME": settings.APP_DISPLAY_NAME,
        "FF_VERSION": settings.FF_VERSION,
        "PLAUSIBLE_SCRIPT_URL": settings.PLAUSIBLE_SCRIPT_URL,
        "PLAUSIBLE_DOMAIN": settings.PLAUSIBLE_DOMAIN,
        "IncidentStatus": IncidentStatus,
    }


def is_during_office_hours(dt: datetime) -> bool:
    """Check whether a datetime is during office hours. 9am-5pm, Mon-Fri.

    Args:
        dt (datetime): datetime with TZ info.
    """
    return (9 <= dt.hour <= 17) and (dt.weekday() < 5)


# Typing for custom HttpRequest classes
# Typing pattern recommended by django-stubs:
# https://github.com/typeddjango/django-stubs#how-can-i-create-a-httprequest-thats-guaranteed-to-have-an-authenticated-user
class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


class AuthenticatedHttpRequest(HttpRequest):
    user: User
