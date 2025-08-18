"""
This module is used to provide configuration, fixtures, and plugins for pytest.
It may be also used for extending doctest's context:
1. https://docs.python.org/3/library/doctest.html
2. https://docs.pytest.org/en/latest/doctest.html
"""

# pylint: disable=redefined-outer-name
from __future__ import annotations

import logging
from importlib import resources as impresources
from typing import Any

import pytest
from django.core.management import call_command
from pytest_django import DjangoDbBlocker
from pytest_django.fixtures import SettingsWrapper
from zipp import Path

from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models import Incident

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _password_hashers(settings: SettingsWrapper) -> None:
    """Forces Django to use fast password hashers for tests."""
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]


@pytest.fixture(autouse=True)
def _debug(settings: SettingsWrapper) -> None:
    """Sets proper DEBUG and TEMPLATE debug mode for coverage of templates."""
    settings.DEBUG = False
    for template in settings.TEMPLATES:
        template["OPTIONS"]["debug"] = True


@pytest.fixture
def footer_text() -> str:
    """An example fixture containing some html fragment."""
    return "Report, manage, escalate!"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup: Any, django_db_blocker: DjangoDbBlocker) -> None:
    # XXX Allow override of fixtures path
    try:
        fixtures_path_mp = impresources.files("firefighter_fixtures")
        fixtures_path = fixtures_path_mp._paths[0]  # type: ignore
    except (ModuleNotFoundError, IndexError, AttributeError):
        # Use the fixtures directory in the project root
        fixtures_path = Path(__file__).parent.parent / "fixtures"
    logger.info(f"Loading fixtures from {fixtures_path}")

    # XXX(dugab): Make sure we load all fixtures
    with django_db_blocker.unblock():
        call_command("loaddata", fixtures_path / "incidents" / "groups.json")
        call_command("loaddata", fixtures_path / "incidents" / "incident_categories.json")
        call_command("loaddata", fixtures_path / "incidents" / "severities.json")
        call_command("loaddata", fixtures_path / "incidents" / "priorities.json")
        call_command("loaddata", fixtures_path / "incidents" / "environments.json")
        call_command("loaddata", fixtures_path / "incidents" / "impact_type.json")
        call_command("loaddata", fixtures_path / "incidents" / "impact_level.json")
        call_command("loaddata", fixtures_path / "incidents" / "milestone_type.json")
        call_command("loaddata", fixtures_path / "incidents" / "metric_type.json")
        call_command(
            "loaddata", fixtures_path / "incidents" / "incident_role_type.json"
        )
    django_db_blocker.restore()


@pytest.fixture
def incident() -> Incident:
    return IncidentFactory.build()


@pytest.fixture
def incident_saved() -> Incident:
    incident: Incident = IncidentFactory.build()
    incident.incident_category.group.save()
    incident.created_by.save()
    incident.save()
    return incident
