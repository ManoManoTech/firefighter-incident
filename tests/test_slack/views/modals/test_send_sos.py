from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Incident
from firefighter.slack.views import SendSosModal

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestSendSosModal:
    @staticmethod
    @pytest.fixture
    def incident() -> Incident:
        """Returns a valid incident."""
        return IncidentFactory.build()

    @staticmethod
    def test_send_sos_modal_build(incident: Incident) -> None:
        modal = SendSosModal()
        res = modal.build_modal_fn(incident)

        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert len(values["blocks"]) == 4

    @staticmethod
    def test_submit_empty_bodied_form(incident: Incident) -> None:
        modal = SendSosModal()
        ack = MagicMock()
        user = UserFactory.build()
        with pytest.raises(TypeError, match="Expected a values dict in the body"):
            modal.handle_modal_fn(ack=ack, body={}, incident=incident, user=user)
