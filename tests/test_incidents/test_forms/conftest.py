"""Fixtures for unified incident form tests."""
from __future__ import annotations

import pytest

from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    UserFactory,
)
from firefighter.incidents.models import Environment, Priority
from firefighter.incidents.models.impact import ImpactLevel, ImpactType, LevelChoices
from firefighter.jira_app.models import JiraUser


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
def impact_level_factory(db):
    """Factory to create ImpactLevel instances."""

    def _create(**kwargs):
        # Handle impact__name syntax by extracting nested parameters
        impact_type_data = {}
        keys_to_remove = []
        for key in list(kwargs.keys()):
            if key.startswith("impact__"):
                nested_key = key.split("__", 1)[1]
                impact_type_data[nested_key] = kwargs[key]
                keys_to_remove.append(key)
        for key in keys_to_remove:
            kwargs.pop(key)

        # Create or get ImpactType
        impact_type = kwargs.pop("impact_type", None)
        if isinstance(impact_type, ImpactType):
            pass  # Already have ImpactType instance
        elif impact_type_data:
            impact_type_name = impact_type_data.get("name", "Test Impact")
            impact_type, _ = ImpactType.objects.get_or_create(name=impact_type_name, defaults={
                "emoji": "📊",
                "help_text": f"Test {impact_type_name} impact",
                "value": impact_type_name.lower().replace(" ", "_"),
                "order": 10,
            })
        else:
            impact_type_name = "Test Impact"
            impact_type, _ = ImpactType.objects.get_or_create(name=impact_type_name, defaults={
                "emoji": "📊",
                "help_text": "Test impact",
                "value": "test_impact",
                "order": 10,
            })

        # Handle value parameter
        value = kwargs.pop("value", LevelChoices.LOW)

        defaults = {
            "impact_type": impact_type,
            "value": value,
            "name": value.label if hasattr(value, "label") else "Test Level",
            "emoji": "📊",
        }
        defaults.update(kwargs)
        return ImpactLevel.objects.create(**defaults)

    return _create


@pytest.fixture
def incident_category_factory(db):
    """Factory to create IncidentCategory instances."""

    def _create(**kwargs):
        return IncidentCategoryFactory(**kwargs)

    return _create


@pytest.fixture
def user_factory(db):
    """Factory to create User instances."""

    def _create(**kwargs):
        return UserFactory(**kwargs)

    return _create


@pytest.fixture
def jira_user_factory(db):
    """Factory to create JiraUser instances."""

    def _create(**kwargs):
        user = kwargs.pop("user", None)
        if user is None:
            user = UserFactory()
        jira_id = kwargs.get("id", f"jira-{user.id}")
        return JiraUser.objects.create(id=jira_id, user=user, **kwargs)

    return _create
