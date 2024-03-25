from __future__ import annotations

from logging import Filter, LogRecord
from typing import TYPE_CHECKING

from loggia.conf import FlexibleFlag, LoggerConfiguration
from loggia.logger import initialize
from loggia.utils.logrecordutils import STANDARD_FIELDS, popattr

from firefighter.firefighter.settings.settings_utils import ENV

if TYPE_CHECKING:
    from collections.abc import Iterable


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


class RemoveExtraDev(Filter):
    def __init__(self, name: str = "", to_ignore: Iterable[str] = ()) -> None:
        self.to_ignore = to_ignore
        super().__init__(name)

    def filter(self, record: LogRecord) -> bool:
        for extra in set(record.__dict__.keys() - STANDARD_FIELDS) & set(
            self.to_ignore
        ):
            popattr(record, extra, None)
        return True


# Explicitely tell Django that we don't want to use its default logging config
LOGGING_CONFIG: None = None
log_cfg = LoggerConfiguration()
log_cfg.capture_loguru = FlexibleFlag.DISABLED
#  From https://docs.djangoproject.com/en/4.2/ref/logging/#django-s-default-logging-configuration
if ENV == "dev":
    log_cfg.set_logger_level("django", "INFO")
    log_cfg.set_logger_level("django.db.backends", "DEBUG")
    log_cfg.set_logger_level("django.server", "INFO")
    log_cfg.set_logger_level("ddtrace", "WARNING")
    log_cfg.set_logger_level("faker.factory", "INFO")
    log_cfg.set_logger_level("fsevents", "INFO")
    log_cfg.set_logger_level("celery.utils.functional", "INFO")
    log_cfg.set_logger_level("celery.bootsteps", "INFO")
    log_cfg.set_logger_level("psycopg.pq", "INFO")
    log_cfg.add_log_filter("gunicorn.access", AccessLogFilter())
    log_cfg.add_log_filter(
        "django.server",
        RemoveExtraDev(to_ignore=("server_time", "status_code", "request")),
    )
    log_cfg.add_log_filter(
        "django.db.backends",
        RemoveExtraDev(to_ignore=("params", "alias", "sql", "duration")),
    )
initialize(log_cfg)
