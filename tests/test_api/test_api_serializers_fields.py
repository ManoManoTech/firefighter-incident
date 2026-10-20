"""Tests for the custom API serializer fields and the incident serializer rendering."""

from __future__ import annotations

from datetime import timedelta

import pytest
from rest_framework.exceptions import ValidationError

from firefighter.api.serializers import (
    CreatableSlugRelatedField,
    DurationFieldSeconds,
    EnvironmentSerializer,
    GroupedModelSerializer,
    IncidentSerializer,
)
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.user import User
from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import JiraTicket


class TestDurationFieldSeconds:
    def test_renders_seconds(self) -> None:
        assert DurationFieldSeconds().to_representation(timedelta(minutes=2)) == 120.0

    def test_parses_seconds(self) -> None:
        assert DurationFieldSeconds().to_internal_value(90) == timedelta(seconds=90)


@pytest.mark.django_db
class TestGroupedModelSerializer:
    @staticmethod
    def test_cannot_be_writable() -> None:
        with pytest.raises(ValueError, match="can only be read_only"):
            GroupedModelSerializer(child_serializer=EnvironmentSerializer, read_only=False)

    @staticmethod
    def test_groups_items_by_key() -> None:
        environments = list(Environment.objects.order_by("value")[:2])
        field = GroupedModelSerializer(
            child_serializer=EnvironmentSerializer, key_getter=lambda env: env.value
        )

        rendered = field.to_representation(environments)

        assert list(rendered) == [env.value for env in environments]
        for env in environments:
            assert rendered[env.value]["name"] == env.name

    @staticmethod
    def test_groups_by_primary_key_by_default() -> None:
        environment = Environment.objects.first()
        assert environment is not None

        rendered = GroupedModelSerializer(
            child_serializer=EnvironmentSerializer
        ).to_representation([environment])

        assert list(rendered) == [str(environment.pk)]


@pytest.mark.django_db
class TestCreatableSlugRelatedField:
    @staticmethod
    def _email_field() -> CreatableSlugRelatedField[User]:
        return CreatableSlugRelatedField[User](
            slug_field="email", queryset=User.objects.all(), allow_null=True
        )

    def test_returns_the_existing_object(self) -> None:
        user = UserFactory.create(email="known@example.com")

        assert self._email_field().run_validation("known@example.com") == user

    def test_creates_a_missing_object(self) -> None:
        created = self._email_field().run_validation("new-reporter@example.com")

        assert created.email == "new-reporter@example.com"
        assert User.objects.filter(email="new-reporter@example.com").exists()

    def test_empty_value_is_returned_as_is(self) -> None:
        assert self._email_field().run_validation(None) is None

    @staticmethod
    def test_wrongly_typed_value_is_invalid() -> None:
        field = CreatableSlugRelatedField[Priority](
            slug_field="value", queryset=Priority.objects.all()
        )

        with pytest.raises(ValidationError):
            field.run_validation("not-a-number")

    def test_missing_queryset_is_invalid(self) -> None:
        field = self._email_field()
        field.queryset = None

        with pytest.raises(ValidationError):
            field.to_internal_value("someone@example.com")

    def test_missing_slug_field_is_a_configuration_error(self) -> None:
        field = self._email_field()
        field.slug_field = None

        with pytest.raises(ValueError, match="requires the `slug_field`"):
            field.to_internal_value("someone@example.com")


def _render(incident_id: int) -> dict[str, object]:
    incident = Incident.objects.get(pk=incident_id)
    incident.metrics_prefetched = []
    incident.costs_prefetched = []
    incident.roles_prefetched = []
    return IncidentSerializer(incident, context={"remove_fields": ["tags"]}).data


@pytest.mark.django_db
class TestIncidentSerializerRendering:
    @staticmethod
    def test_renders_an_incident_without_jira_ticket() -> None:
        incident = IncidentFactory.create()

        data = _render(incident.id)

        assert "tags" not in data
        assert data["status"] == incident.status.label
        assert data["jira_ticket_key"] is None
        assert data["jira_ticket_url"] is None
        assert data["metrics"] == {}
        assert data["slack_channel_name"] == (
            f"#{incident.slack_channel_name}" if incident.slack_channel_name else ""
        )

    @staticmethod
    def test_renders_the_jira_ticket() -> None:
        incident = IncidentFactory.create()
        reporter = JiraUser.objects.create(id="jira-reporter", user=incident.created_by)
        ticket = JiraTicket.objects.create(
            id=4242, key="INC-4242", summary="s", reporter=reporter, incident=incident
        )

        data = _render(incident.id)

        assert data["jira_ticket_key"] == "INC-4242"
        assert data["jira_ticket_url"] == ticket.url
