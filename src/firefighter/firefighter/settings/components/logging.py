from __future__ import annotations

from logging import Filter, Formatter, LogRecord
from typing import Any

from firefighter.firefighter.settings.settings_utils import ENV, config
from firefighter.logging.custom_json_formatter import (
    CustomJsonEncoder,
    CustomJsonFormatter,
)
from firefighter.logging.pretty_formatter import PrettyFormatter


class AccessLogFilter(Filter):
    """Filter Gunicorn.access logs to avoid logging static files and healthcheck requests logging."""

    def filter(self, record: LogRecord) -> bool:
        if not record.args:
            return True

        raw_uri: str = record.args["{raw_uri}e"]  # type: ignore

        if (
            raw_uri == "/api/v2/firefighter/monitoring/healthcheck"
            and record.levelno <= 20
        ):
            return False
        if raw_uri.startswith("/static/") and record.levelno <= 20:
            return False
        if raw_uri == "/favicon.ico" and record.levelno <= 30:  # noqa: SIM103
            return False
        return True


def get_json_formatter() -> dict[str, type[Formatter] | Any]:
    attr_whitelist = {"name", "levelname", "pathname", "lineno", "funcName"}
    attrs = [x for x in CustomJsonFormatter.RESERVED_ATTRS if x not in attr_whitelist]
    return {
        "()": CustomJsonFormatter,
        "json_indent": None,
        "json_encoder": CustomJsonEncoder,
        "reserved_attrs": attrs,
        "timestamp": True,
    }


base_level = "DEBUG" if ENV == "dev" else "INFO"
base_level_override = config("LOG_LEVEL", cast=str, default="")
if base_level_override and base_level_override != "":
    base_level = base_level_override.upper()

formatter: dict[str, type[Formatter] | Any]
formatter = {"()": PrettyFormatter} if ENV == "dev" else get_json_formatter()

FF_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dynamicfmt": formatter,
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "dynamicfmt"},
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "propagate": False,
        },
        "watchfiles.main": {"level": "INFO"},
        "django.utils.autoreload": {"level": "INFO"},
        "django.request": {"handlers": ["console"], "propagate": False},
        "django.server": {"handlers": ["console"], "propagate": False},
        "django.template": {"handlers": ["console"], "propagate": False},
        "django.db.backends": {
            "handlers": ["console"],
            "propagate": False,
            "level": base_level,
        },
        "django.db.backends.schema": {"handlers": ["console"], "propagate": False},
        "gunicorn.access": {
            "handlers": ["console"],
            "filters": ["accessfilter"],
            "propagate": False,
        },
        "gunicorn.error": {"handlers": ["console"], "propagate": False},
        "ddtrace": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "faker.factory": {
            "level": "INFO",
        },
        "fsevents": {
            "level": "INFO",
        },
    },
    "filters": {"accessfilter": {"()": AccessLogFilter}},
    "root": {
        "handlers": ["console"],
        "level": base_level,
        "propagate": False,
    },
}

LOGGING = FF_LOGGING
