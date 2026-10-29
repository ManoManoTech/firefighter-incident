"""Early closure only rejects: a real incident, even a partner's, follows the normal workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.enums import (
    OFFERED_CLOSURE_REASONS,
    ClosureReason,
    IncidentOrigin,
    IncidentStatus,
)
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.slack.views.modals.closure_reason import ClosureReasonModal

RESPOND = "firefighter.slack.views.modals.closure_reason.respond"


def _body(incident: Incident, reason: str) -> dict[str, Any]:
    values: dict[str, Any] = {
        "closure_reason": {
            "select_closure_reason": {"selected_option": {"value": reason}}
        },
        "closure_reference": {"input_closure_reference": {"value": ""}},
        "closure_message": {"input_closure_message": {"value": "Closing early"}},
    }
    return {
        "view": {"state": {"values": values}, "private_metadata": str(incident.id)},
        "user": {"id": "U123456"},
    }


@pytest.fixture
def incident() -> Incident:
    return IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)


@pytest.mark.django_db
class TestEarlyClosureRejects:
    @staticmethod
    @pytest.mark.parametrize("reason", OFFERED_CLOSURE_REASONS)
    def test_every_offered_reason_rejects(
        mocker: Any, incident: Incident, reason: ClosureReason
    ) -> None:
        mocker.patch(RESPOND)

        result = ClosureReasonModal().handle_modal_fn(
            ack=MagicMock(),
            body=_body(incident, reason),
            incident=incident,
            user=UserFactory.create(),
        )

        assert result is True
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.REJECTED
        assert incident.closure_reason == reason
        assert incident.origin == IncidentOrigin.INTERNAL
        assert incident.partner is None

    @staticmethod
    @pytest.mark.parametrize("reason", [ClosureReason.RESOLVED, ClosureReason.EXTERNAL])
    def test_a_real_incident_is_never_closed_early(
        mocker: Any, incident: Incident, reason: ClosureReason
    ) -> None:
        """Views opened before the deploy still offer these reasons: they are refused."""
        mocker.patch(RESPOND)
        ack = MagicMock()

        result = ClosureReasonModal().handle_modal_fn(
            ack=ack,
            body=_body(incident, reason),
            incident=incident,
            user=UserFactory.create(),
        )

        assert result is False
        assert "closure_reason" in ack.call_args.kwargs["errors"]
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.INVESTIGATING
        assert not incident.closure_reason


@pytest.mark.django_db
class TestEarlyClosureModal:
    @staticmethod
    def test_offers_only_rejection_reasons_and_no_origin(incident: Incident) -> None:
        view = ClosureReasonModal().build_modal_fn(body={}, incident=incident).to_dict()

        block_ids = [block.get("block_id") for block in view["blocks"]]
        reason_block = view["blocks"][block_ids.index("closure_reason")]
        reasons = [o["value"] for o in reason_block["element"]["options"]]
        assert reasons == [r.value for r in OFFERED_CLOSURE_REASONS]
        assert ClosureReason.RESOLVED not in reasons
        assert ClosureReason.EXTERNAL not in reasons
        assert not {"closure_origin", "closure_partner", "closure_new_partner"} & set(
            block_ids
        )

    @staticmethod
    def test_the_mandatory_message_follows_the_reason(incident: Incident) -> None:
        view = ClosureReasonModal().build_modal_fn(body={}, incident=incident).to_dict()

        inputs = [b["block_id"] for b in view["blocks"] if b["type"] == "input"]
        assert inputs == ["closure_reason", "closure_message", "closure_reference"]
