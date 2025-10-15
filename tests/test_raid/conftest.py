"""Pytest fixtures for RAID tests."""

from __future__ import annotations

import factory
import pytest
from factory.django import DjangoModelFactory

from firefighter.incidents.factories import IncidentFactory, UserFactory


class JiraUserFactory(DjangoModelFactory):
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
    reporter = factory.SubFactory(JiraUserFactory)
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
    return JiraUserFactory


@pytest.fixture
def jira_ticket_factory():
    """Pytest fixture for JiraTicketFactory."""
    return JiraTicketFactory
