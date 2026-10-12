from __future__ import annotations

import logging
import time
from functools import cache
from typing import Any, Never

from django.core.cache import caches
from django.core.exceptions import BadRequest, PermissionDenied
from django.db import connection
from django.db.models import Model
from django.db.utils import OperationalError
from django.http import Http404, HttpRequest, JsonResponse
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_safe
from django.views.generic import DetailView

from firefighter.firefighter.tasks import CELERY_HEARTBEAT_CACHE_KEY

logger = logging.getLogger(__name__)

CELERY_HEARTBEAT_MAX_AGE = 5 * 60
"""Seconds after which the last heartbeat is too old: beat schedules one every
minute, the margin absorbs beat or worker restarts."""


def _check_db() -> bool:
    try:
        connection.ensure_connection()
    except OperationalError:
        logger.exception("Healthcheck failed: can't access DB!")
        return False
    return True


def _check_redis() -> bool:
    try:
        redis_cache = caches["default"]
        redis_cache.set("_healthcheck", "1", timeout=10)
        return redis_cache.get("_healthcheck") == "1"
    except Exception:
        logger.exception("Healthcheck failed: can't access Redis!")
        return False


def _check_celery() -> bool:
    """Check that a worker recently ran the heartbeat task scheduled by beat.

    Pinging the workers is not reliable: with the gevent pool, the worker stops
    answering broadcast commands for good once their idle Redis connection is
    closed (e.g. by a proxy idle timeout), while it keeps consuming tasks.
    """
    try:
        last_heartbeat = caches["default"].get(CELERY_HEARTBEAT_CACHE_KEY)
    except Exception:
        logger.exception("Healthcheck failed: can't read the Celery heartbeat!")
        return False
    if last_heartbeat is None:
        logger.error("Healthcheck failed: no Celery heartbeat recorded!")
        return False
    age = time.time() - last_heartbeat
    if age > CELERY_HEARTBEAT_MAX_AGE:
        logger.error(
            "Healthcheck failed: last Celery heartbeat is %d seconds old!", age
        )
        return False
    return True


@require_safe
def healthcheck(request: HttpRequest) -> JsonResponse:
    """Liveness probe: checks DB only (used by Kubernetes)."""
    db_ok = _check_db()
    if db_ok:
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "fail"}, status=503)


@require_safe
def readiness(request: HttpRequest) -> JsonResponse:
    """Readiness probe: checks all dependencies (DB, Redis, Celery workers)."""
    checks = {
        "db": _check_db(),
        "redis": _check_redis(),
        "celery": _check_celery(),
    }
    healthy = all(checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "fail", "checks": checks},
        status=200 if healthy else 503,
    )


def permission_denied_view(request: HttpRequest) -> Never:
    raise PermissionDenied("Permission denied")


def not_found_view(request: HttpRequest) -> Never:
    raise Http404("Not found")


def bad_request_view(request: HttpRequest) -> Never:
    raise BadRequest("Unknown parameters")


def server_error_view(request: HttpRequest) -> Never:
    # pylint: disable=broad-exception-raised
    raise Exception("Test exception for 500")  # noqa: TRY002


class CustomDetailView[MT: Model](DetailView[MT]):
    """A custom detail view that adds the admin edit URL to the context, as `admin_edit_url`."""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        obj: MT = context[self.get_context_object_name(self.object) or "object"]
        return {**context, "admin_edit_url": get_admin_edit_url(self.model, obj.pk)}


@cache
def get_admin_edit_url(model_class: type[Model], object_pk: Any) -> str | None:
    """Construct the URL name for the admin edit page using the model's app_label and model_name."""
    app_label: str = model_class._meta.app_label  # noqa: SLF001
    model_name = model_class._meta.model_name  # noqa: SLF001
    url_name: str = f"admin:{app_label}_{model_name}_change"

    try:
        return reverse(url_name, args=[object_pk])
    except NoReverseMatch:
        return None
