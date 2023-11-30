from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from factory import Iterator, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyInteger

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models import (
    Component,
    Environment,
    Group,
    Incident,
    Priority,
    User,
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    name = Faker("name")
    email = Faker("email")
    username = Faker("user_name")


class GroupFactory(DjangoModelFactory):
    class Meta:
        model = Group

    name = Faker("text", max_nb_chars=20)
    description = Faker("text", max_nb_chars=50)
    order = FuzzyInteger(100, 1000)


class SeverityFactory(DjangoModelFactory):
    class Meta:
        model = Priority

    name = Faker("text", max_nb_chars=20)
    value = FuzzyInteger(0, 100)
    order = FuzzyInteger(100, 1000)


class EnvironmentFactory(DjangoModelFactory):
    class Meta:
        model = Environment

    name = Faker("text", max_nb_chars=20)
    description = Faker("text", max_nb_chars=50)
    order = FuzzyInteger(100, 1000)


class ComponentFactory(DjangoModelFactory):
    class Meta:
        model = Component

    name = Faker("text", max_nb_chars=30)
    description = Faker("text", max_nb_chars=50)
    order = FuzzyInteger(100, 1000)
    group = SubFactory(GroupFactory)


class IncidentFactory(DjangoModelFactory):
    class Meta:
        model = Incident

    id = Sequence(lambda n: n + 1)
    title = Faker("text", max_nb_chars=50)
    description = Faker("text")
    _status = FuzzyChoice(IncidentStatus.choices, getter=lambda c: c[0])
    created_at = FuzzyDateTime(
        start_dt=datetime(2018, 1, 1, tzinfo=timezone.get_current_timezone()),
        end_dt=datetime(2022, 1, 1, tzinfo=timezone.get_current_timezone()),
    )
    updated_at = LazyAttribute(
        lambda inc: datetime(
            inc.created_at.year,
            inc.created_at.month,
            inc.created_at.day,
            tzinfo=timezone.get_current_timezone(),
        )
    )
    component = Iterator(Component.objects.all())
    priority = Iterator(Priority.objects.all())
    environment = Iterator(Environment.objects.all())

    created_by = SubFactory(UserFactory)
