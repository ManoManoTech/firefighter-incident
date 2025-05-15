"""Collection of custom Django template filters. They are added as built-in filters and thus can be used in templates of any app."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

import markdown as md
import nh3
from django.template.defaulttags import register as register_base

if TYPE_CHECKING:
    from collections.abc import Callable

    from django import template

register_global: template.Library = cast("template.Library", register_base)
V = TypeVar("V")


@register_global.filter
def timedelta_chop_microseconds(delta: timedelta) -> timedelta:
    """Removes microseconds from a timedelta object.

    Args:
        delta (timedelta): The timedelta object to remove microseconds from.

    Returns:
        timedelta: A new timedelta object with microseconds removed.
    """
    return delta - timedelta(microseconds=delta.microseconds)


@register_global.filter
def get_item(dictionary: dict[str, Any], key: Any) -> Any:
    """Get the value of a key from a dictionary or object.

    Args:
        dictionary (dict[str, Any]): The dictionary or object to get the value from.
        key (Any): The key to get the value for.

    Returns:
        Any: The value of the key in the dictionary or object.
    """
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    if hasattr(dictionary, "__getitem__"):
        try:
            return dictionary[key]
        except KeyError:
            pass
    if hasattr(dictionary, "get"):
        return dictionary.get(key)
    if not isinstance(dictionary, dict):
        dictionary = dictionary.__dict__  # type: ignore

    return dictionary.get(key)


@register_global.filter
def apply_filter(
    value: Any,
    fn_holder: dict[Literal["filter_args", "filter"], Callable[..., V]],
) -> V | Any:
    """Applies a filter function to a given value.

    Args:
        value: The value to be filtered.
        fn_holder: A dictionary containing the filter function and its arguments.

    Returns:
        The filtered value.
    """
    fn = fn_holder.get("filter")

    if not fn:
        return value

    args = fn_holder.get("filter_args")
    if args:
        return fn(value, args)
    return fn(value)


@register_global.filter
def readable_time_delta(delta: timedelta) -> str:
    """Format a time delta as a string. Ignore seconds and microseconds
    From https://github.com/wimglenn/readabledelta/blob/master/readabledelta.py (The Unlicense).
    """
    negative = delta < timedelta(0)
    delta = abs(delta)

    # Other allowed values are  "seconds", "milliseconds", "microseconds".
    keys = [
        "weeks",
        "days",
        "hours",
        "minutes",
    ]

    # datetime.timedelta are normalized internally in Python to the units days, seconds, microseconds allowing a unique
    # representation.  This is not the only possible basis; the calculations below rebase onto more human friendly keys
    # noinspection PyDictCreation
    data = {}
    # rebase days onto weeks, days
    data["weeks"], data["days"] = divmod(delta.days, 7)
    # rebase seconds onto hours, minutes, seconds
    data["hours"], data["seconds"] = divmod(delta.seconds, 60 * 60)
    data["minutes"], data["seconds"] = divmod(data["seconds"], 60)
    # rebase microseconds onto milliseconds, microseconds

    if data["weeks"] != 0 or data["days"] != 0:
        keys.remove("minutes")
        keys.remove("hours")

    output = [
        f"{data[k]} {k[:-1] if data[k] == 1 else k}" for k in keys if data[k] != 0
    ]

    if not output:
        result = "an instant"
    elif len(output) == 1:
        [result] = output
    else:
        left, right = output[:-1], output[-1:]
        result = ", ".join(left) + " and " + right[0]

    if negative:
        return "-" + result
    return result


@register_global.filter
def markdown(text: str) -> str:
    """Converts markdown-formatted text to HTML.

    Sanitize the HTML to only allow a subset of tags.

    Args:
        text (str): The markdown-formatted text to convert.

    Returns:
        str: The HTML-formatted text.
    """
    return nh3.clean(md.markdown(text, output_format="html"), tags=nh3.ALLOWED_TAGS)
