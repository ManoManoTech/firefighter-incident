from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.incidents.models import Environment, Priority


def create_unique_priority(value: int, *, needs_postmortem: bool = False) -> Priority:
    """Create a Priority with unique constraints handled properly."""
    return Priority.objects.create(
        value=value,
        name=f"Priority-{value}-{uuid.uuid4().hex[:8]}",
        order=value,
        needs_postmortem=needs_postmortem,
        description=f"Test priority {value}"
    )


def create_unique_environment(value: str, *, exact_value: bool = False) -> Environment:
    """Create an Environment with unique constraints handled properly.

    Args:
        value: Base value for the environment
        exact_value: If True, use the value exactly and get_or_create (for testing specific logic)
    """
    if exact_value:
        # For testing specific environment logic, use exact value with get_or_create
        # This handles the case where fixtures already created an environment with this value
        unique_suffix = uuid.uuid4().hex[:8]
        environment, _ = Environment.objects.get_or_create(
            value=value,  # Exact value needed for logic testing
            defaults={
                "name": f"Environment {value} {unique_suffix}",
                "description": f"Test environment {value} {unique_suffix}"
            }
        )
        return environment

    # Default case: create unique environment
    unique_suffix = uuid.uuid4().hex[:8]
    return Environment.objects.create(
        value=f"{value}-{unique_suffix}",
        name=f"Environment {value} {unique_suffix}",
        description=f"Test environment {value} {unique_suffix}"
    )


@pytest.mark.django_db
class TestMitigatedReopeningWorkflow(TestCase):
    """Test the new workflow allowing reopening from MITIGATED status."""

    def test_p1_mitigated_allows_reopening_and_postmortem(self):
        """P1 incidents should be able to go to POST_MORTEM OR reopen to INVESTIGATING/MITIGATING."""
        # Create P1 priority with needs_postmortem=True
        priority = create_unique_priority(value=1001, needs_postmortem=True)
        # IMPORTANT: Use exact "PRD" value for environment since requires_postmortem logic checks for exact match
        environment = create_unique_environment("PRD", exact_value=True)

        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )
        form = UpdateStatusForm(incident=incident)

        # Get available statuses
        status_choices = dict(form.fields["status"].choices)
        available_statuses = {IncidentStatus(int(k)) for k in status_choices}

        # P1 incidents should have POST_MORTEM (required for P1/P2)
        assert IncidentStatus.POST_MORTEM in available_statuses
        # P1 incidents should ALSO have direct reopening options (NEW behavior)
        assert IncidentStatus.INVESTIGATING in available_statuses
        assert IncidentStatus.MITIGATING in available_statuses

    def test_can_reopen_from_mitigated_to_mitigating_p3(self):
        """P3 incidents can return from MITIGATED to MITIGATING."""
        priority = create_unique_priority(value=3001, needs_postmortem=False)
        environment = create_unique_environment("STG")

        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )
        form = UpdateStatusForm(incident=incident)

        # Get available statuses
        status_choices = dict(form.fields["status"].choices)
        available_statuses = {IncidentStatus(int(k)) for k in status_choices}

        # Should include both return options and CLOSED
        assert IncidentStatus.INVESTIGATING in available_statuses
        assert IncidentStatus.MITIGATING in available_statuses
        assert IncidentStatus.CLOSED in available_statuses
        # P3 should not include POST_MORTEM
        assert IncidentStatus.POST_MORTEM not in available_statuses

    def test_form_validation_requires_message_for_reopening(self):
        """Form validation requires message when reopening from MITIGATED."""
        priority = create_unique_priority(value=5001, needs_postmortem=False)
        environment = create_unique_environment("INT")

        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Test without message - should fail
        form_data = {
            "status": str(IncidentStatus.INVESTIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": str(incident.incident_category.id),
            "message": "",  # Empty message should cause validation error
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is False, f"Form should be invalid but got valid=True, errors={form.errors}"
        assert "message" in form.errors

    def test_form_validation_requires_minimum_message_length(self):
        """Form validation requires minimum message length for reopening."""
        priority = create_unique_priority(value=5002, needs_postmortem=False)
        environment = create_unique_environment("INT")

        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Test with message too short - should fail
        form_data = {
            "status": str(IncidentStatus.INVESTIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": str(incident.incident_category.id),
            "message": "short",  # Less than 10 chars
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is False
        assert "message" in form.errors

    def test_form_validation_accepts_valid_reopening_message(self):
        """Form validation accepts valid message for reopening."""
        priority = create_unique_priority(value=5003, needs_postmortem=False)
        environment = create_unique_environment("INT")

        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Test with valid message - should pass
        form_data = {
            "status": str(IncidentStatus.INVESTIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": str(incident.incident_category.id),
            "message": "Investigation revealed additional issues requiring further analysis",
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is True

    def test_form_validation_normal_transitions_unaffected(self):
        """Normal transitions not from MITIGATED should be unaffected."""
        priority = create_unique_priority(value=5004, needs_postmortem=False)
        environment = create_unique_environment("INT")

        # Test from INVESTIGATING to MITIGATING (normal flow)
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            priority=priority,
            environment=environment
        )

        form_data = {
            "status": str(IncidentStatus.MITIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": str(incident.incident_category.id),
            "message": "",  # Empty message should be OK for normal transitions
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is True
