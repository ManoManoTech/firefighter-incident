"""Pytest fixtures for RAID tests."""

from __future__ import annotations

import factory
import pytest
from factory.django import DjangoModelFactory

from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models import Environment, Priority


class JiraUserFactoryClass(DjangoModelFactory):
    """Factory for JiraUser model."""

    class Meta:
        model = "jira_app.JiraUser"
        django_get_or_create = ("id",)

    id = factory.Sequence(lambda n: f"jira-user-{n}")
    user = factory.SubFactory(UserFactory)


class JiraTicketFactory(DjangoModelFactory):
    """Factory for JiraTicket model."""

    class Meta:
        model = "raid.JiraTicket"

    id = factory.Sequence(lambda n: 10000 + n)
    key = factory.Sequence(lambda n: f"INC-{n}")
    summary = "Test Jira Ticket"
    description = "Test description for Jira ticket"
    reporter = factory.SubFactory(JiraUserFactoryClass)
    incident = None


@pytest.fixture
def user_factory():
    """Pytest fixture for UserFactory."""
    return UserFactory


@pytest.fixture
def incident_factory():
    """Pytest fixture for IncidentFactory."""
    return IncidentFactory


@pytest.fixture
def jira_user_factory():
    """Pytest fixture for JiraUserFactory."""
    return JiraUserFactoryClass


@pytest.fixture
def jira_ticket_factory():
    """Pytest fixture for JiraTicketFactory."""
    return JiraTicketFactory


@pytest.fixture
def priority_factory(db):
    """Factory to create Priority instances."""

    def _create(**kwargs):
        value = kwargs.get("value", 1)
        name = kwargs.get("name", f"P{value}")
        set_as_default = kwargs.get("default", False)

        # If default=True, clear any other defaults first
        if set_as_default:
            Priority.objects.filter(default=True).update(default=False)

        defaults = {
            "emoji": "🔴",
            "order": value,
            "default": set_as_default,
            "enabled_create": True,
            "enabled_update": True,
            "needs_postmortem": value <= 2,  # P1-P2 need postmortem
        }
        # Remove name and value from kwargs if present
        kwargs_copy = kwargs.copy()
        kwargs_copy.pop("name", None)
        kwargs_copy.pop("value", None)
        defaults.update(kwargs_copy)

        priority, created = Priority.objects.get_or_create(
            name=name,
            value=value,
            defaults=defaults,
        )

        # If already exists and we want it as default, just set that
        if not created and set_as_default:
            priority.default = True
            priority.save(update_fields=["default"])

        return priority

    return _create


@pytest.fixture
def environment_factory(db):
    """Factory to create Environment instances."""

    def _create(**kwargs):
        value = kwargs.get("value", "TST")
        set_as_default = kwargs.get("default", False)

        # If default=True, clear any other defaults first
        if set_as_default:
            Environment.objects.filter(default=True).update(default=False)

        defaults = {
            "description": f"Environment {value}",
            "order": 1,
            "default": set_as_default,
        }
        # Remove value and default from kwargs if present
        kwargs_copy = kwargs.copy()
        kwargs_copy.pop("value", None)
        kwargs_copy.pop("default", None)
        defaults.update(kwargs_copy)

        environment, created = Environment.objects.get_or_create(
            value=value,
            defaults=defaults,
        )

        # If already exists and we want it as default, just set that
        if not created and set_as_default:
            environment.default = True
            environment.save(update_fields=["default"])

        return environment

    return _create


@pytest.fixture
def incident_category_factory(db):
    """Factory to create IncidentCategory instances."""

    def _create(**kwargs):
        return IncidentCategoryFactory(**kwargs)

    return _create
