"""The origin fields of the Close, Edit and Key Events forms."""

from __future__ import annotations

import pytest

from firefighter.incidents.enums import IncidentOrigin, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.forms.close_incident import CloseIncidentForm
from firefighter.incidents.forms.edit import EditMetaForm
from firefighter.incidents.forms.timeline import (
    IncidentTimelineForm,
    KeyEventsTimelineForm,
)
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.partner import Partner


def _close_data(incident: Incident, **extra: str) -> dict[str, str]:
    return {
        "title": "A title long enough",
        "description": "A summary long enough",
        "incident_category": str(incident.incident_category.id),
        **extra,
    }


@pytest.mark.django_db
class TestCloseForm:
    @staticmethod
    def test_a_partner_origin_needs_a_partner() -> None:
        incident = IncidentFactory.create()

        form = CloseIncidentForm(data=_close_data(incident, origin="partner"))

        assert not form.is_valid()
        # No partner exists yet: the error goes on "add a partner"
        assert "new_partner" in form.errors

    @staticmethod
    def test_saves_the_picked_partner() -> None:
        incident = IncidentFactory.create()
        user = UserFactory.create()
        algolia = Partner.objects.create(name="Algolia", slug="algolia")

        form = CloseIncidentForm(
            data=_close_data(incident, origin="partner", partner=str(algolia.id))
        )
        assert form.is_valid(), form.errors

        assert form.save_origin_fields(incident, user)
        incident.refresh_from_db()
        assert incident.origin == IncidentOrigin.PARTNER
        assert incident.partner == algolia

    @staticmethod
    def test_no_origin_submitted_leaves_it_unchanged() -> None:
        incident = IncidentFactory.create()

        form = CloseIncidentForm(data=_close_data(incident))
        assert form.is_valid(), form.errors

        assert not form.save_origin_fields(incident, None)


@pytest.mark.django_db
class TestEditForm:
    @staticmethod
    def test_a_typed_partner_is_created_and_saved() -> None:
        incident = IncidentFactory.create()
        environment = Environment.objects.first()
        assert environment is not None

        form = EditMetaForm(
            data={
                "title": "A title long enough",
                "description": "A summary long enough",
                "environment": [str(environment.id)],
                "origin": "partner",
                "new_partner": "Cloudflare",
            }
        )
        assert form.is_valid(), form.errors

        form.save_origin_fields(incident, UserFactory.create())
        incident.refresh_from_db()
        assert incident.partner is not None
        assert incident.partner.name == "Cloudflare"


@pytest.mark.django_db
class TestKeyEventsForm:
    @staticmethod
    def test_offers_the_partner_list_but_no_text_input() -> None:
        Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = KeyEventsTimelineForm(incident=incident, user=UserFactory.create())

        assert "key_event_origin" in form.fields
        assert "key_event_partner" in form.fields
        assert "key_event_new_partner" not in form.fields

    @staticmethod
    def test_saving_the_origin_records_it() -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = IncidentTimelineForm(
            data={"origin": "partner", "partner": str(algolia.id)},
            incident=incident,
            user=UserFactory.create(),
        )
        assert form.is_valid(), form.errors
        form.save()

        incident.refresh_from_db()
        assert incident.origin == IncidentOrigin.PARTNER
        assert incident.partner == algolia

    @staticmethod
    def test_a_partner_origin_can_be_set_before_the_partner() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        form = IncidentTimelineForm(
            data={"origin": "partner"}, incident=incident, user=UserFactory.create()
        )
        assert form.is_valid(), form.errors
        form.save()

        incident.refresh_from_db()
        assert incident.origin == IncidentOrigin.PARTNER
        assert incident.partner is None
