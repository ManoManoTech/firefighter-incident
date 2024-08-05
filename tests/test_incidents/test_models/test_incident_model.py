from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis.extra import django
from hypothesis.strategies import builds

from firefighter.incidents.factories import IncidentFactory

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident


@pytest.mark.django_db
class TestIncident(django.TestCase):
    """This is a property-based test that ensures model correctness."""

    @given(builds(IncidentFactory.build))
    def test_model_properties(self, instance: Incident) -> None:
        """Tests that instance can be saved and has correct representation."""
        instance.component.group.save()
        instance.component.save()
        instance.environment.save()
        instance.priority.save()
        instance.created_by.save()
        instance.save()

        assert instance.id > 0
