from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django_celery_beat.schedulers import ModelEntry

from firefighter.firefighter.celery_client import app as celery_app
from firefighter.firefighter.tasks import CELERY_HEARTBEAT_CACHE_KEY, celery_heartbeat
from firefighter.firefighter.views import CELERY_HEARTBEAT_MAX_AGE

if TYPE_CHECKING:
    from django.test import Client
    from pytest_django.fixtures import SettingsWrapper

READINESS_URL = "/api/v2/firefighter/monitoring/readiness"


@pytest.fixture(autouse=True)
def _local_memory_cache(settings: SettingsWrapper) -> None:
    """Isolate the tests from Redis and from each other."""
    settings.CACHES = {
        **settings.CACHES,
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    }
    caches["default"].clear()


def test_celery_heartbeat_records_timestamp() -> None:
    before = time.time()

    celery_heartbeat()

    assert caches["default"].get(CELERY_HEARTBEAT_CACHE_KEY) >= before


def test_beat_schedules_registered_heartbeat_task() -> None:
    entry = celery_app.conf.beat_schedule["celery-heartbeat"]

    assert entry["task"] == celery_heartbeat.name
    assert entry["schedule"] < CELERY_HEARTBEAT_MAX_AGE


@pytest.mark.django_db
def test_beat_sends_heartbeat_with_expiration() -> None:
    """The entry goes through DatabaseScheduler, which silently drops unknown options."""
    entry = ModelEntry.from_entry(
        "celery-heartbeat",
        app=celery_app,
        **celery_app.conf.beat_schedule["celery-heartbeat"],
    )

    assert entry.options["expires"] == 60


@pytest.mark.django_db
def test_readiness_ok_with_recent_heartbeat(client: Client) -> None:
    celery_heartbeat()

    response = client.get(READINESS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"db": True, "redis": True, "celery": True},
    }


@pytest.mark.django_db
def test_readiness_fails_without_heartbeat(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = client.get(READINESS_URL)

    assert response.status_code == 503
    assert response.json()["checks"]["celery"] is False
    assert "no Celery heartbeat recorded" in caplog.text


@pytest.mark.django_db
def test_readiness_fails_with_stale_heartbeat(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    caches["default"].set(
        CELERY_HEARTBEAT_CACHE_KEY,
        time.time() - CELERY_HEARTBEAT_MAX_AGE - 1,
        timeout=None,
    )

    with caplog.at_level(logging.ERROR):
        response = client.get(READINESS_URL)

    assert response.status_code == 503
    assert response.json()["checks"]["celery"] is False
    assert "last Celery heartbeat is" in caplog.text


@pytest.mark.django_db
def test_readiness_fails_when_heartbeat_unreadable(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        patch.object(caches["default"], "get", side_effect=ConnectionError),
        caplog.at_level(logging.ERROR),
    ):
        response = client.get(READINESS_URL)

    assert response.status_code == 503
    assert response.json()["checks"]["celery"] is False
    assert "can't read the Celery heartbeat" in caplog.text
