"""Early closure asks whether the incident was real: real ones are CLOSED with an origin, others REJECTED."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from firefighter.incidents.enums import ClosureReason, IncidentOrigin, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.partner import Partner
from firefighter.slack.views.modals.closure_reason import ClosureReasonModal

RESPOND = "firefighter.slack.views.modals.closure_reason.respond"


def _body(
    incident: Incident,
    reason: str,
    *,
    origin: str | None = None,
    partner: Partner | None = None,
    new_partner: str | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "closure_reason": {
            "select_closure_reason": {"selected_option": {"value": reason}}
        },
        "closure_reference": {"input_closure_reference": {"value": ""}},
        "closure_message": {"input_closure_message": {"value": "Closing early"}},
        "closure_new_partner": {"input_closure_new_partner": {"value": new_partner}},
    }
    if origin is not None:
        values["closure_origin"] = {
            "select_closure_origin": {"selected_option": {"value": origin}}
        }
    if partner is not None:
        values["closure_partner"] = {
            "select_closure_partner": {"selected_option": {"value": str(partner.id)}}
        }
    return {
        "view": {"state": {"values": values}, "private_metadata": str(incident.id)},
        "user": {"id": "U123456"},
    }


@pytest.fixture
def incident() -> Incident:
    return IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)


@pytest.mark.django_db
class TestEarlyClosureOfARealIncident:
    @staticmethod
    def test_records_the_partner_and_closes(mocker: Any, incident: Incident) -> None:
        mocker.patch(RESPOND)
        algolia = Partner.objects.create(name="Algolia", slug="algolia")

        result = ClosureReasonModal().handle_modal_fn(
            ack=MagicMock(),
            body=_body(
                incident, ClosureReason.RESOLVED, origin="partner", partner=algolia
            ),
            incident=incident,
            user=UserFactory.create(),
        )

        assert result is True
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CLOSED
        assert incident.origin == IncidentOrigin.PARTNER
        assert incident.partner == algolia

    @staticmethod
    def test_a_typed_partner_is_added_to_the_list(
        mocker: Any, incident: Incident
    ) -> None:
        mocker.patch(RESPOND)

        ClosureReasonModal().handle_modal_fn(
            ack=MagicMock(),
            body=_body(
                incident, ClosureReason.RESOLVED, origin="partner", new_partner="Zyte"
            ),
            incident=incident,
            user=UserFactory.create(),
        )

        incident.refresh_from_db()
        assert incident.partner is not None
        assert incident.partner.name == "Zyte"
        assert not incident.partner.is_reviewed

    @staticmethod
    def test_a_partner_origin_needs_a_partner(mocker: Any, incident: Incident) -> None:
        mocker.patch(RESPOND)
        ack = MagicMock()

        result = ClosureReasonModal().handle_modal_fn(
            ack=ack,
            body=_body(incident, ClosureReason.RESOLVED, origin="partner"),
            incident=incident,
            user=UserFactory.create(),
        )

        assert result is False
        ack.assert_called_once()
        assert "closure_new_partner" in ack.call_args.kwargs["errors"]
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.INVESTIGATING

    @staticmethod
    def test_internal_by_default(mocker: Any, incident: Incident) -> None:
        mocker.patch(RESPOND)

        ClosureReasonModal().handle_modal_fn(
            ack=MagicMock(),
            body=_body(incident, ClosureReason.RESOLVED),
            incident=incident,
            user=UserFactory.create(),
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CLOSED
        assert incident.origin == IncidentOrigin.INTERNAL


@pytest.mark.django_db
class TestEarlyClosureOfANonIncident:
    @staticmethod
    def test_is_rejected_and_its_origin_ignored(
        mocker: Any, incident: Incident
    ) -> None:
        mocker.patch(RESPOND)
        algolia = Partner.objects.create(name="Algolia", slug="algolia")

        ClosureReasonModal().handle_modal_fn(
            ack=MagicMock(),
            body=_body(
                incident, ClosureReason.DUPLICATE, origin="partner", partner=algolia
            ),
            incident=incident,
            user=UserFactory.create(),
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.REJECTED
        assert incident.closure_reason == ClosureReason.DUPLICATE
        assert incident.origin == IncidentOrigin.INTERNAL
        assert incident.partner is None


@pytest.mark.django_db
class TestEarlyClosureModal:
    @staticmethod
    def test_asks_whether_the_incident_was_real_and_offers_the_partners(
        incident: Incident,
    ) -> None:
        Partner.objects.create(name="Algolia", slug="algolia")
        Partner.objects.create(name="Old", slug="old", is_active=False)

        view = ClosureReasonModal().build_modal_fn(body={}, incident=incident).to_dict()

        blocks = {block.get("block_id"): block for block in view["blocks"]}
        reasons = [o["value"] for o in blocks["closure_reason"]["element"]["options"]]
        assert reasons[0] == ClosureReason.RESOLVED
        assert ClosureReason.EXTERNAL not in reasons
        assert (
            blocks["closure_origin"]["element"]["initial_option"]["value"] == "internal"
        )
        partners = [
            o["text"]["text"] for o in blocks["closure_partner"]["element"]["options"]
        ]
        assert partners == ["Algolia"]
        assert "closure_new_partner" in blocks
