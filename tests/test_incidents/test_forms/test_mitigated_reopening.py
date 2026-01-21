from __future__ import annotations

import pytest
import uuid
from django.test import TestCase

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.incidents.models import Priority, Environment


def create_unique_priority(value: int, needs_postmortem: bool = False) -> Priority:
    """Create a Priority with unique constraints handled properly."""
    return Priority.objects.create(
        value=value,
        name=f"Priority-{value}-{uuid.uuid4().hex[:8]}",
        order=value,
        needs_postmortem=needs_postmortem,
        description=f"Test priority {value}"
    )


def create_unique_environment(value: str, exact_value: bool = False) -> Environment:
    """Create an Environment with unique constraints handled properly.
    
    Args:
        value: Base value for the environment
        exact_value: If True, use the value exactly and get_or_create (for testing specific logic)
    """
    if exact_value:
        # For testing specific environment logic, use exact value with get_or_create
        # This handles the case where fixtures already created an environment with this value
        unique_suffix = uuid.uuid4().hex[:8]
        environment, created = Environment.objects.get_or_create(
            value=value,  # Exact value needed for logic testing
            defaults={
                'name': f"Environment {value} {unique_suffix}",
                'description': f"Test environment {value} {unique_suffix}"
            }
        )
        return environment
    else:
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
        available_statuses = {IncidentStatus(int(k)) for k in status_choices.keys()}

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
        available_statuses = {IncidentStatus(int(k)) for k in status_choices.keys()}

        # Should include both return options and CLOSED
        assert IncidentStatus.INVESTIGATING in available_statuses
        assert IncidentStatus.MITIGATING in available_statuses
        assert IncidentStatus.CLOSED in available_statuses
        # P3 should not include POST_MORTEM
        assert IncidentStatus.POST_MORTEM not in available_statuses

    def test_requires_reopening_reason_from_mitigated_to_investigating(self):
        """Reopening from MITIGATED to INVESTIGATING requires a reason."""
        priority = create_unique_priority(value=4001, needs_postmortem=False)
        environment = create_unique_environment("QA")
        
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Should require reason
        assert (
            UpdateStatusForm.requires_reopening_reason(
                incident, IncidentStatus.INVESTIGATING
            )
            is True
        )
        assert (
            UpdateStatusForm.requires_reopening_reason(
                incident, IncidentStatus.MITIGATING
            )
            is True
        )

        # Should NOT require reason for other transitions
        assert (
            UpdateStatusForm.requires_reopening_reason(
                incident, IncidentStatus.POST_MORTEM
            )
            is False
        )
        assert (
            UpdateStatusForm.requires_reopening_reason(incident, IncidentStatus.CLOSED)
            is False
        )

    def test_requires_reopening_reason_only_from_mitigated(self):
        """Reopening reason is only required from MITIGATED status."""
        # Test from other statuses - should NOT require reason
        for status in [
            IncidentStatus.OPEN,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
        ]:
            # Create unique values for each iteration
            priority = create_unique_priority(value=5000 + status.value, needs_postmortem=False)
            environment = create_unique_environment(f"TEST-{status.value}")
            incident = IncidentFactory.create(
                _status=status,
                priority=priority,
                environment=environment
            )
            assert (
                UpdateStatusForm.requires_reopening_reason(
                    incident, IncidentStatus.INVESTIGATING
                )
                is False
            )

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
            "incident_category": (
                str(incident.incident_category.id) if incident.incident_category else ""
            ),
            "message": "",  # Empty message
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is False
        assert "message" in form.errors
        assert "justification message is required" in form.errors["message"][0].lower()

    def test_form_validation_requires_minimum_message_length(self):
        """Form validation requires minimum 10 characters for reopening message."""
        priority = create_unique_priority(value=6001, needs_postmortem=False)
        environment = create_unique_environment("DEVTEST")
        
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Test with too short message - should fail
        form_data = {
            "status": str(IncidentStatus.INVESTIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": (
                str(incident.incident_category.id) if incident.incident_category else ""
            ),
            "message": "short",  # Too short
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is False
        assert "message" in form.errors
        assert "at least 10 characters" in form.errors["message"][0].lower()

    def test_form_validation_accepts_valid_reopening_message(self):
        """Form validation accepts valid message when reopening from MITIGATED."""
        priority = create_unique_priority(value=7001, needs_postmortem=False)
        environment = create_unique_environment("VALID")
        
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        # Test with valid message - should pass
        form_data = {
            "status": str(IncidentStatus.INVESTIGATING.value),
            "priority": str(incident.priority.id),
            "incident_category": (
                str(incident.incident_category.id) if incident.incident_category else ""
            ),
            "message": "Team identified additional issues requiring investigation",
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        assert form.is_valid() is True

    def test_form_validation_normal_transitions_unaffected(self):
        """Normal transitions don't require special message validation."""
        # Test forward progression - should not require special validation
        # Use PRD environment since POST_MORTEM requires both needs_postmortem=True AND environment='PRD'
        priority = create_unique_priority(value=8001, needs_postmortem=True)
        environment = create_unique_environment("PRD", exact_value=True)
        
        incident = IncidentFactory.create(
            _status=IncidentStatus.MITIGATED,
            priority=priority,
            environment=environment
        )

        form_data = {
            "status": str(IncidentStatus.POST_MORTEM.value),
            "priority": str(incident.priority.id),
            "incident_category": (
                str(incident.incident_category.id) if incident.incident_category else ""
            ),
            "message": "",  # Empty message is OK for normal transitions
        }
        form = UpdateStatusForm(data=form_data, incident=incident)

        # Should be valid - no special message requirement for forward transitions
        assert form.is_valid() is True
