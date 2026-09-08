"""Tests for the debounced re-sync of a corrected timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.signals import incident_key_events_updated
from firefighter.slack.tasks.sync_timeline import (
    _DEBOUNCE_KEY,
    cache,
    schedule_timeline_sync,
    sync_corrected_timeline,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models.incident import Incident


@pytest.fixture(autouse=True)
def _clear_debounce_keys() -> None:
    cache.clear()


@pytest.mark.django_db
class TestScheduleTimelineSync:
    @staticmethod
    def test_a_burst_of_edits_schedules_a_single_sync(mocker: MockerFixture) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        apply_async = mocker.patch(
            "firefighter.slack.tasks.sync_timeline.sync_corrected_timeline.apply_async"
        )

        armed = [schedule_timeline_sync(incident) for _ in range(4)]

        assert armed == [True, False, False, False]
        apply_async.assert_called_once()

    @staticmethod
    def test_each_incident_gets_its_own_window(mocker: MockerFixture) -> None:
        first: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        second: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        apply_async = mocker.patch(
            "firefighter.slack.tasks.sync_timeline.sync_corrected_timeline.apply_async"
        )

        assert schedule_timeline_sync(first) is True
        assert schedule_timeline_sync(second) is True

        assert apply_async.call_count == 2

    @staticmethod
    def test_the_window_reopens_once_the_sync_has_run(mocker: MockerFixture) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        mocker.patch(
            "firefighter.slack.tasks.sync_timeline.sync_corrected_timeline.apply_async"
        )
        schedule_timeline_sync(incident)

        sync_corrected_timeline(incident.id)

        assert schedule_timeline_sync(incident) is True


@pytest.mark.django_db
class TestSyncCorrectedTimeline:
    @staticmethod
    def test_recomputes_metrics_and_fans_out_the_signal(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        compute_metrics = mocker.patch(
            "firefighter.incidents.models.incident.Incident.compute_metrics"
        )
        received: list[int] = []

        def _receiver(sender: object, incident: Incident, **kwargs: object) -> None:
            received.append(incident.id)

        incident_key_events_updated.connect(_receiver)
        try:
            sync_corrected_timeline(incident.id)
        finally:
            incident_key_events_updated.disconnect(_receiver)

        compute_metrics.assert_called_once_with()
        assert received == [incident.id]

    @staticmethod
    def test_drops_the_debounce_key_so_later_edits_are_not_swallowed() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        key = _DEBOUNCE_KEY.format(incident_id=incident.id)
        cache.set(key, 1, timeout=300)

        sync_corrected_timeline(incident.id)

        assert cache.get(key) is None

    @staticmethod
    def test_unknown_incident_is_a_no_op() -> None:
        # The incident could have been deleted between the edit and the sync.
        sync_corrected_timeline(-1)
