from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import PropertyMock, patch

import pytest
from hypothesis import given
from hypothesis.extra import django
from hypothesis.strategies import builds

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models import IncidentUpdate
from firefighter.jira_app.models import JiraPostMortem

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models import Incident


@pytest.mark.django_db
class TestIncident(django.TestCase):
    """This is a property-based test that ensures model correctness."""

    @given(builds(IncidentFactory.build))
    def test_model_properties(self, instance: Incident) -> None:
        """Tests that instance can be saved and has correct representation."""
        instance.incident_category.group.save()
        instance.incident_category.save()
        instance.environment.save()
        instance.priority.save()
        instance.created_by.save()
        instance.save()

        assert instance.id > 0


@pytest.mark.django_db
class TestIncidentCanBeClosed:
    """Test the can_be_closed property logic."""

    def test_cannot_close_incident_below_mitigated_status(self) -> None:
        """Test that incidents below MITIGATED status cannot be closed without reason."""
        # Create an incident in INVESTIGATING status (below MITIGATED)
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        can_close, reasons = incident.can_be_closed

        assert can_close is False
        assert any(reason[0] == "STATUS_NOT_MITIGATED" for reason in reasons)
        assert any("Mitigated" in reason[1] for reason in reasons)

    def test_can_close_incident_at_mitigated_status(self) -> None:
        """Test that incidents at MITIGATED status can be closed (if no postmortem required)."""
        # Create a P3 incident in MITIGATED status (no postmortem required)
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority__value=3,  # P3 doesn't require postmortem
        )

        can_close, reasons = incident.can_be_closed

        # Should be closable (assuming no missing milestones)
        assert can_close is True or "STATUS_NOT_MITIGATED" not in [
            r[0] for r in reasons
        ]

    def test_can_close_incident_with_closure_reason(self) -> None:
        """Test that incidents with closure_reason can always be closed."""
        # Create an incident in early status but with closure reason
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            closure_reason=ClosureReason.DUPLICATE,
        )

        can_close, reasons = incident.can_be_closed

        assert can_close is True
        assert reasons == []

    def test_cannot_close_when_jira_postmortem_not_ready(self, settings: None) -> None:
        """Block closure if Jira post-mortem exists but is not in Ready status."""
        settings.ENABLE_JIRA_POSTMORTEM = True
        incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            priority__value=1,
            priority__needs_postmortem=True,
            environment__value="PRD",
        )
        JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INC-999",
            jira_issue_id="999",
            created_by=incident.created_by,
        )
        incident.refresh_from_db()
        assert hasattr(incident, "jira_postmortem_for")

        with (
            patch.object(
                type(incident),
                "needs_postmortem",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(type(incident), "missing_milestones", return_value=[]),
            patch(
                "firefighter.jira_app.service_postmortem.jira_postmortem_service.is_postmortem_ready",
                return_value=(False, "In Progress"),
            ),
        ):
            can_close, reasons = incident.can_be_closed

        assert can_close is False
        assert any(r[0] == "POSTMORTEM_NOT_READY" for r in reasons)

    def test_postmortem_ready_allows_closure(
        self, mocker: MockerFixture, settings: None
    ) -> None:
        """When Jira PM is Ready, can_be_closed should allow closure for PM incidents."""
        settings.ENABLE_JIRA_POSTMORTEM = True
        incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            priority__value=1,
            priority__needs_postmortem=True,
            environment__value="PRD",
        )
        JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INC-READY",
            jira_issue_id="123",
            created_by=incident.created_by,
        )

        mocker.patch.object(type(incident), "missing_milestones", return_value=[])
        mocker.patch(
            "firefighter.jira_app.service_postmortem.jira_postmortem_service.is_postmortem_ready",
            return_value=(True, "Ready"),
        )

        can_close, reasons = incident.can_be_closed

        assert can_close is True
        assert reasons == []

    def test_postmortem_status_unknown_sets_reason(
        self, mocker: MockerFixture, settings: None
    ) -> None:
        """Errors while checking Jira PM should return POSTMORTEM_STATUS_UNKNOWN."""
        settings.ENABLE_JIRA_POSTMORTEM = True
        incident = IncidentFactory.create(
            _status=IncidentStatus.POST_MORTEM,
            priority__value=1,
            priority__needs_postmortem=True,
            environment__value="PRD",
        )
        JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key="INC-ERR",
            jira_issue_id="124",
            created_by=incident.created_by,
        )
        incident.refresh_from_db()
        assert hasattr(incident, "jira_postmortem_for")

        mocker.patch.object(type(incident), "missing_milestones", return_value=[])
        mocker.patch(
            "firefighter.jira_app.service_postmortem.jira_postmortem_service.is_postmortem_ready",
            side_effect=Exception("boom"),
        )
        mocker.patch.object(
            type(incident),
            "needs_postmortem",
            new_callable=PropertyMock,
            return_value=True,
        )

        can_close, reasons = incident.can_be_closed

        assert can_close is False
        assert any(r[0] == "POSTMORTEM_STATUS_UNKNOWN" for r in reasons)


@pytest.mark.django_db
class TestIncidentSetStatus:
    """Test the set_status method logic."""

    def test_set_status_to_mitigated_creates_recovered_event(self) -> None:
        """Test that setting status to MITIGATED creates a 'recovered' event."""
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)

        # Set status to MITIGATED using create_incident_update
        incident.create_incident_update(
            status=IncidentStatus.MITIGATED.value,
            created_by=incident.created_by,
            message="Incident has been mitigated",
        )

        # Check that a 'recovered' event was created
        recovered_event = IncidentUpdate.objects.filter(
            incident=incident, event_type="recovered"
        ).first()

        assert recovered_event is not None
        assert recovered_event.event_type == "recovered"


@pytest.mark.django_db
class TestIncidentNeedsPostmortem:
    """Test the needs_postmortem property logic.

    NOTE: The needs_postmortem property checks if:
    1. Priority requires postmortem (P1/P2)
    2. Environment is PRD
    3. At least one post-mortem system is enabled (Confluence OR Jira)
    """

    def test_p3_does_not_need_postmortem(self) -> None:
        """Test that P3 incident does not require postmortem even in PRD."""
        incident = IncidentFactory.create(
            priority__value=3,  # P3
            priority__needs_postmortem=False,
            environment__value="PRD",
        )
        assert incident.needs_postmortem is False

    def test_p1_non_prd_does_not_need_postmortem(self) -> None:
        """Test that P1 incident in non-PRD environment does not require postmortem."""
        incident = IncidentFactory.create(
            priority__value=1,  # P1
            priority__needs_postmortem=True,
            environment__value="STG",  # Use STG instead of DEV
        )
        assert incident.needs_postmortem is False
