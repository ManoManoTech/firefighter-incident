"""Tests for the `dedup_key` idempotency constraint on Incident.

The partial unique index guarantees at most one *open* incident
(``_status <= MITIGATED``) per ``dedup_key``. NULL keys never collide, and once
an incident leaves the open window (Post-mortem / Closed) the key is freed for a
future recurrence.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models.incident import Incident

DEDUP_KEY = "mon:108013180:pim_offer:stg"


@pytest.mark.django_db
class TestIncidentDedupKeyConstraint:
    def test_two_open_incidents_cannot_share_dedup_key(self) -> None:
        IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN)
        with pytest.raises(IntegrityError):
            IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN)

    def test_mitigated_incident_still_blocks_same_dedup_key(self) -> None:
        # MITIGATED (40) is still inside the "open" window (<= 40).
        IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.MITIGATED)
        with pytest.raises(IntegrityError):
            IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN)

    def test_dedup_key_is_freed_once_past_open_window(self) -> None:
        first = IncidentFactory.create(dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN)
        # Move past the open window (Post-mortem = 50 > 40) without triggering
        # model save side effects.
        Incident.objects.filter(pk=first.pk).update(_status=IncidentStatus.POST_MORTEM)
        # A new open incident with the same key is now allowed.
        second = IncidentFactory.create(
            dedup_key=DEDUP_KEY, _status=IncidentStatus.OPEN
        )
        assert second.pk != first.pk

    def test_null_dedup_key_never_collides(self) -> None:
        first = IncidentFactory.create(dedup_key=None, _status=IncidentStatus.OPEN)
        second = IncidentFactory.create(dedup_key=None, _status=IncidentStatus.OPEN)
        assert first.pk != second.pk
