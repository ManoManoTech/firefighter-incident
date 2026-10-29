"""Incident origin (internal / partner), the partner list and the REJECTED status."""

from __future__ import annotations

import importlib
from io import StringIO
from unittest.mock import MagicMock

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction

from firefighter.incidents.enums import (
    ClosureReason,
    IncidentOrigin,
    IncidentStatus,
    status_for_closure_reason,
)
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.partner import Partner
from firefighter.incidents.origin import (
    ORIGIN_UPDATED_EVENT_TYPE,
    apply_origin,
    origin_label,
    resolve_partner,
)
from firefighter.incidents.signals import (
    incident_closed,
    incident_origin_updated,
    partner_created,
)
from firefighter.incidents.views.reports import get_incident_by_status_chart_data

backfill = importlib.import_module(
    "firefighter.incidents.migrations.0040_backfill_rejected_status_and_origin"
)


class TestStatusRules:
    @staticmethod
    @pytest.mark.parametrize(
        ("reason", "expected"),
        [
            (ClosureReason.RESOLVED, IncidentStatus.CLOSED),
            (ClosureReason.EXTERNAL, IncidentStatus.CLOSED),
            (None, IncidentStatus.CLOSED),
            (ClosureReason.DUPLICATE, IncidentStatus.REJECTED),
            (ClosureReason.FALSE_POSITIVE, IncidentStatus.REJECTED),
            (ClosureReason.SUPERSEDED, IncidentStatus.REJECTED),
            (ClosureReason.CANCELLED, IncidentStatus.REJECTED),
        ],
    )
    def test_status_for_closure_reason(
        reason: str | None, expected: IncidentStatus
    ) -> None:
        assert status_for_closure_reason(reason) == expected

    @staticmethod
    def test_only_closed_and_rejected_are_terminal() -> None:
        assert {s for s in IncidentStatus if s.is_terminal} == {
            IncidentStatus.CLOSED,
            IncidentStatus.REJECTED,
        }


@pytest.mark.django_db
class TestPartnerList:
    @staticmethod
    def test_a_typed_name_reuses_the_existing_partner_whatever_its_case() -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")

        partner, created = Partner.objects.get_or_create_by_name("  ALGOLIA ")

        assert partner == algolia
        assert not created

    @staticmethod
    def test_a_new_name_creates_a_partner_to_review() -> None:
        user = UserFactory.create()

        partner, created = Partner.objects.get_or_create_by_name(
            "Microsoft  Azure (OpenAI)", created_by=user
        )

        assert created
        assert partner.name == "Microsoft Azure (OpenAI)"
        assert partner.slug == "microsoft-azure-openai"
        assert partner.is_active
        assert not partner.is_reviewed
        assert partner.created_by == user

    @staticmethod
    def test_an_empty_name_is_refused() -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            Partner.objects.get_or_create_by_name("   ")

    @staticmethod
    def test_names_are_unique_whatever_their_case() -> None:
        Partner.objects.create(name="Stripe", slug="stripe")
        with pytest.raises(IntegrityError), transaction.atomic():
            Partner.objects.create(name="STRIPE", slug="stripe-2")

    @staticmethod
    def test_create_partners_command_is_idempotent_and_marks_them_reviewed() -> None:
        call_command("create_partners", "Algolia", "Cloudflare", stdout=StringIO())
        out = StringIO()

        call_command("create_partners", "algolia", "Stripe", stdout=out)

        assert sorted(Partner.objects.values_list("name", flat=True)) == [
            "Algolia",
            "Cloudflare",
            "Stripe",
        ]
        assert all(Partner.objects.values_list("is_reviewed", flat=True))
        assert "Already exists: Algolia" in out.getvalue()


@pytest.mark.django_db
class TestApplyOrigin:
    @staticmethod
    def test_records_who_set_a_partner_origin_and_tells_listeners() -> None:
        incident = IncidentFactory.create()
        user = UserFactory.create()
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        listener = MagicMock()
        incident_origin_updated.connect(listener)
        try:
            changed = apply_origin(incident, IncidentOrigin.PARTNER, algolia, user=user)
        finally:
            incident_origin_updated.disconnect(listener)

        assert changed
        incident.refresh_from_db()
        assert incident.origin == IncidentOrigin.PARTNER
        assert incident.partner == algolia
        update = IncidentUpdate.objects.get(
            incident=incident, event_type=ORIGIN_UPDATED_EVENT_TYPE
        )
        assert update.created_by == user
        assert update.message == "Origin set to Partner: Algolia"
        listener.assert_called_once()
        assert listener.call_args.kwargs["user"] == user

    @staticmethod
    def test_internal_origin_drops_the_partner() -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create(
            origin=IncidentOrigin.PARTNER, partner=algolia
        )

        apply_origin(incident, IncidentOrigin.INTERNAL, algolia, user=None)

        incident.refresh_from_db()
        assert incident.origin == IncidentOrigin.INTERNAL
        assert incident.partner is None

    @staticmethod
    def test_an_unchanged_origin_records_nothing() -> None:
        incident = IncidentFactory.create()

        assert not apply_origin(incident, IncidentOrigin.INTERNAL, None, user=None)
        assert not IncidentUpdate.objects.filter(
            incident=incident, event_type=ORIGIN_UPDATED_EVENT_TYPE
        ).exists()

    @staticmethod
    def test_a_partner_requires_a_partner_origin_in_the_database() -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create()
        incident.partner = algolia
        with pytest.raises(IntegrityError), transaction.atomic():
            incident.save()

    @staticmethod
    @pytest.mark.parametrize(
        ("origin", "partner_name", "label"),
        [
            (IncidentOrigin.INTERNAL, None, "Internal"),
            (IncidentOrigin.PARTNER, None, "Partner (unspecified)"),
            (IncidentOrigin.PARTNER, "Stripe", "Partner: Stripe"),
        ],
    )
    def test_origin_label(origin: str, partner_name: str | None, label: str) -> None:
        partner = (
            Partner.objects.create(name=partner_name, slug=partner_name.lower())
            if partner_name
            else None
        )
        incident = IncidentFactory.build(origin=origin, partner=partner)

        assert origin_label(incident) == label


@pytest.mark.django_db
class TestResolvePartner:
    @staticmethod
    def test_a_selected_partner_wins_over_a_typed_name() -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create()

        assert (
            resolve_partner(algolia, "Cloudflare", user=None, incident=incident)
            == algolia
        )
        assert not Partner.objects.filter(name="Cloudflare").exists()

    @staticmethod
    def test_a_typed_new_partner_is_created_and_announced() -> None:
        incident = IncidentFactory.create()
        user = UserFactory.create()
        listener = MagicMock()
        partner_created.connect(listener)
        try:
            partner = resolve_partner(None, "Zyte", user=user, incident=incident)
        finally:
            partner_created.disconnect(listener)

        assert partner is not None
        assert partner.name == "Zyte"
        listener.assert_called_once()
        assert listener.call_args.kwargs["incident"] == incident

    @staticmethod
    def test_nothing_picked_nor_typed_gives_no_partner() -> None:
        incident = IncidentFactory.create()

        assert resolve_partner(None, "  ", user=None, incident=incident) is None


@pytest.mark.django_db
class TestRejectedIncident:
    @staticmethod
    def test_rejecting_an_incident_sends_the_closing_signal() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        listener = MagicMock()
        incident_closed.connect(listener)
        try:
            incident.create_incident_update(
                created_by=UserFactory.create(), status=IncidentStatus.REJECTED
            )
        finally:
            incident_closed.disconnect(listener)

        listener.assert_called_once()


@pytest.mark.django_db
class TestBackfillMigration:
    @staticmethod
    def test_rejects_the_incidents_closed_as_not_real_and_flags_external_ones() -> None:
        duplicate = IncidentFactory.create(
            _status=IncidentStatus.CLOSED, closure_reason=ClosureReason.DUPLICATE
        )
        closing_update = IncidentUpdate.objects.create(
            incident=duplicate,
            _status=IncidentStatus.CLOSED,
            event_type="closure_reason",
        )
        external = IncidentFactory.create(
            _status=IncidentStatus.CLOSED, closure_reason=ClosureReason.EXTERNAL
        )
        resolved = IncidentFactory.create(
            _status=IncidentStatus.CLOSED, closure_reason=ClosureReason.RESOLVED
        )
        real = IncidentFactory.create(_status=IncidentStatus.CLOSED)

        backfill.forwards(apps, None)

        duplicate.refresh_from_db()
        closing_update.refresh_from_db()
        assert duplicate.status == IncidentStatus.REJECTED
        assert closing_update.status == IncidentStatus.REJECTED
        external.refresh_from_db()
        assert external.status == IncidentStatus.CLOSED
        assert external.origin == IncidentOrigin.PARTNER
        assert external.partner is None
        for incident in (resolved, real):
            incident.refresh_from_db()
            assert incident.status == IncidentStatus.CLOSED
            assert incident.origin == IncidentOrigin.INTERNAL

    @staticmethod
    def test_backwards_restores_closed_and_internal() -> None:
        rejected: Incident = IncidentFactory.create(
            closure_reason=ClosureReason.CANCELLED
        )
        Incident.objects.filter(id=rejected.id).update(_status=IncidentStatus.REJECTED)
        external = IncidentFactory.create(
            closure_reason=ClosureReason.EXTERNAL, origin=IncidentOrigin.PARTNER
        )

        backfill.backwards(apps, None)

        rejected.refresh_from_db()
        external.refresh_from_db()
        assert rejected.status == IncidentStatus.CLOSED
        assert external.origin == IncidentOrigin.INTERNAL


@pytest.mark.django_db
class TestReports:
    @staticmethod
    def test_the_status_chart_counts_rejected_incidents_apart() -> None:
        IncidentFactory.create(_status=IncidentStatus.CLOSED)
        rejected = IncidentFactory.create(closure_reason=ClosureReason.DUPLICATE)
        Incident.objects.filter(id=rejected.id).update(_status=IncidentStatus.REJECTED)

        chart = get_incident_by_status_chart_data(Incident.objects.all())

        values = dict(zip(chart["keys"], chart["values"], strict=True))
        assert values["Closed"] == 1
        assert values["Rejected"] == 1
