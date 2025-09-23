from __future__ import annotations

import operator
from datetime import datetime

from django.utils import timezone
from factory import Iterator, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyInteger

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models import (
    Environment,
    Group,
    Incident,
    IncidentCategory,
    Priority,
    User,
)


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User

    name = Faker("name")  # type: ignore[no-untyped-call]
    email = Faker("email")  # type: ignore[no-untyped-call]
    username = Faker("user_name")  # type: ignore[no-untyped-call]


class GroupFactory(DjangoModelFactory[Group]):
    class Meta:
        model = Group

    name = Faker("text", max_nb_chars=20)  # type: ignore[no-untyped-call]
    description = Faker("text", max_nb_chars=50)  # type: ignore[no-untyped-call]
    order = FuzzyInteger(100, 1000)  # type: ignore[no-untyped-call]


class PriorityFactory(DjangoModelFactory[Priority]):
    """Factory for creating Priority instances in tests.

    Creates Priority objects with random values. Use specific values in tests
    when testing priority-specific behavior (e.g., P1-P5 JIRA mapping).
    """
    class Meta:
        model = Priority

    name = Faker("text", max_nb_chars=20)  # type: ignore[no-untyped-call]
    value = FuzzyInteger(0, 100)  # type: ignore[no-untyped-call]
    order = FuzzyInteger(100, 1000)  # type: ignore[no-untyped-call]


# Legacy alias - will be removed when Severity model is removed
SeverityFactory = PriorityFactory


class EnvironmentFactory(DjangoModelFactory[Environment]):
    class Meta:
        model = Environment

    name = Faker("text", max_nb_chars=20)  # type: ignore[no-untyped-call]
    description = Faker("text", max_nb_chars=50)  # type: ignore[no-untyped-call]
    order = FuzzyInteger(100, 1000)  # type: ignore[no-untyped-call]


class IncidentCategoryFactory(DjangoModelFactory[IncidentCategory]):
    class Meta:
        model = IncidentCategory

    name = Faker("text", max_nb_chars=30)  # type: ignore[no-untyped-call]
    description = Faker("text", max_nb_chars=50)  # type: ignore[no-untyped-call]
    order = FuzzyInteger(100, 1000)  # type: ignore[no-untyped-call]
    group = SubFactory(GroupFactory)  # type: ignore[no-untyped-call]


class IncidentFactory(DjangoModelFactory[Incident]):
    class Meta:
        model = Incident

    id = Sequence(lambda n: n + 1)  # type: ignore[no-untyped-call]
    title = Faker("text", max_nb_chars=50)  # type: ignore[no-untyped-call]
    description = Faker("text")  # type: ignore[no-untyped-call]
    _status = FuzzyChoice(IncidentStatus.choices, getter=operator.itemgetter(0))  # type: ignore[no-untyped-call]
    created_at = FuzzyDateTime(
        start_dt=datetime(2018, 1, 1, tzinfo=timezone.get_current_timezone()),
        end_dt=datetime(2022, 1, 1, tzinfo=timezone.get_current_timezone()),
    )  # type: ignore[no-untyped-call]
    updated_at = LazyAttribute(
        lambda inc: datetime(
            inc.created_at.year,
            inc.created_at.month,
            inc.created_at.day,
            tzinfo=timezone.get_current_timezone(),
        )
    )  # type: ignore[no-untyped-call]
    incident_category = Iterator(IncidentCategory.objects.all())  # type: ignore[no-untyped-call]
    priority = Iterator(Priority.objects.all())  # type: ignore[no-untyped-call]
    environment = Iterator(Environment.objects.all())  # type: ignore[no-untyped-call]

    created_by = SubFactory(UserFactory)  # type: ignore[no-untyped-call]
