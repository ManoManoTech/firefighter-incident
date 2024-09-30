from __future__ import annotations

import logging

import pytest
from pytest_mock import MockerFixture

from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models import Incident, IncidentUpdate
from firefighter.slack.views.modals.status import StatusModal

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestStatusModal:
    @staticmethod
    @pytest.fixture
    def incident() -> Incident:
        """Returns a valid incident."""
        return IncidentFactory.build()

    @staticmethod
    def test_status_modal_build(incident: Incident, mocker: MockerFixture) -> None:
        mocker.patch.object(
            StatusModal,
            "get_latest_update",
            return_value=IncidentUpdate(incident=incident, message="test"),
        )
        modal = StatusModal()
        res = modal.build_modal_fn(incident=incident)

        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert len(values["blocks"]) == 7

    @staticmethod
    def test_status_modal_build_no_message(
        incident: Incident, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            StatusModal,
            "get_latest_update",
            return_value=IncidentUpdate(incident=incident),
        )
        modal = StatusModal()
        res = modal.build_modal_fn(incident=incident)

        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert len(values["blocks"]) == 4

    @staticmethod
    def test_status_modal_build_no_update(
        incident: Incident, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            StatusModal,
            "get_latest_update",
            return_value=None,
        )
        modal = StatusModal()
        with pytest.raises(ValueError, match="No update found for incident"):
            modal.build_modal_fn(incident=incident)
