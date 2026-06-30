"""Tests for the idempotent create path in ``IncidentSerializer``.

When ``declare()`` hits the partial unique constraint (an open incident already
exists for the given ``dedup_key``), the serializer returns the existing incident
and flags it so the view answers HTTP 200 instead of 201.

``declare()`` is patched to raise ``IntegrityError`` directly, isolating the
serializer's conflict-handling branch from DB/severity setup.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.db import IntegrityError

from firefighter.api.serializers import IncidentSerializer
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory

DEDUP_KEY = "mon:108013180:pim_offer:stg"


@pytest.mark.django_db
def test_create_returns_existing_open_incident_on_conflict() -> None:
    existing = IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN)
    serializer = IncidentSerializer()

    with patch(
        "firefighter.api.serializers.Incident.objects.declare",
        side_effect=IntegrityError("duplicate key value"),
    ):
        result = serializer.create(
            {"dedup_key": DEDUP_KEY, "title": "t", "description": "d"}
        )

    assert result.pk == existing.pk
    assert getattr(result, "_idempotent_hit", False) is True


@pytest.mark.django_db
def test_create_reraises_when_no_matching_open_incident() -> None:
    serializer = IncidentSerializer()

    with (
        patch(
            "firefighter.api.serializers.Incident.objects.declare",
            side_effect=IntegrityError("some other integrity error"),
        ),
        pytest.raises(IntegrityError),
    ):
        serializer.create(
            {"dedup_key": "no-such-open-key", "title": "t", "description": "d"}
        )


@pytest.mark.django_db
def test_create_reraises_when_no_dedup_key() -> None:
    serializer = IncidentSerializer()

    with (
        patch(
            "firefighter.api.serializers.Incident.objects.declare",
            side_effect=IntegrityError("unrelated"),
        ),
        pytest.raises(IntegrityError),
    ):
        serializer.create({"title": "t", "description": "d"})
