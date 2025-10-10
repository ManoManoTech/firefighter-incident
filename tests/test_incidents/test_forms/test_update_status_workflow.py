"""Test the status workflow logic for update status form."""
from __future__ import annotations

import pytest
from django.apps import apps
from django.test import TestCase

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.incidents.models import Environment, Priority


@pytest.mark.django_db
class TestUpdateStatusWorkflow(TestCase):
    """Test that status choices respect workflow rules."""

    def test_p1_p2_cannot_skip_postmortem(self):
        """P1/P2 incidents cannot go directly from Mitigated to Closed."""

        # Get existing P1 or P2 priority that needs post-mortem
        p1_priority = Priority.objects.filter(
            value=1, needs_postmortem=True
        ).first()

        if not p1_priority:
            # If P1 doesn't exist, try P2
            p1_priority = Priority.objects.filter(
                value=2, needs_postmortem=True
            ).first()

        if not p1_priority:
            # Skip test if no priority needing postmortem exists
            pytest.skip("No P1/P2 priority with needs_postmortem=True found in database")

        # Get PRD environment (required for needs_postmortem to be True)
        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found in database")

        # Create an incident with P1/P2 priority in Mitigated status with PRD env
        incident = IncidentFactory.create(
            priority=p1_priority,
            environment=prd_env,
            _status=IncidentStatus.MITIGATED,
        )

        # Note: incident.needs_postmortem also requires firefighter.confluence to be installed
        # For testing, we'll check the underlying conditions directly
        if apps.is_installed("firefighter.confluence"):
            assert incident.needs_postmortem, "Incident should need postmortem (P1/P2 + PRD)"

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that CLOSED is not in the choices
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED not in status_choices
        assert IncidentStatus.POST_MORTEM in status_choices

    def test_p1_p2_can_close_from_postmortem(self):
        """P1/P2 incidents can go from Post-mortem to Closed."""

        # Get existing P1 or P2 priority that needs post-mortem
        p2_priority = Priority.objects.filter(
            value__in=[1, 2], needs_postmortem=True
        ).first()

        if not p2_priority:
            pytest.skip("No P1/P2 priority with needs_postmortem=True found in database")

        # Get PRD environment
        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found in database")

        # Create an incident with P1/P2 priority in Post-mortem status with PRD env
        incident = IncidentFactory.create(
            priority=p2_priority,
            environment=prd_env,
            _status=IncidentStatus.POST_MORTEM,
        )

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that CLOSED is in the choices
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED in status_choices

    def test_p3_plus_can_skip_postmortem(self):
        """P3+ incidents can go directly from Mitigated to Closed and should not have post-mortem."""
        # Get existing P3+ priority that doesn't need post-mortem
        p3_priority = Priority.objects.filter(
            value__gte=3, needs_postmortem=False
        ).first()

        if not p3_priority:
            # If no P3+ without postmortem, skip the test
            pytest.skip("No P3+ priority with needs_postmortem=False found in database")

        # Create an incident with P3+ priority in Mitigated status
        incident = IncidentFactory.create(
            priority=p3_priority,
            _status=IncidentStatus.MITIGATED,
        )

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that CLOSED is in the choices for P3+ but POST_MORTEM is NOT
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED in status_choices
        assert IncidentStatus.POST_MORTEM not in status_choices, "P3+ incidents should not have post-mortem status available"

    def test_p1_p2_cannot_skip_postmortem_from_mitigating(self):
        """P1/P2 incidents cannot go directly from Mitigating to Closed."""

        # Get existing P1 or P2 priority that needs post-mortem
        p1_priority = Priority.objects.filter(
            value__in=[1, 2], needs_postmortem=True
        ).first()

        if not p1_priority:
            pytest.skip("No P1/P2 priority with needs_postmortem=True found in database")

        # Get PRD environment (required for needs_postmortem to be True)
        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found in database")

        # Create an incident with P1/P2 priority in MITIGATING (Mitigating) status with PRD env
        incident = IncidentFactory.create(
            priority=p1_priority,
            environment=prd_env,
            _status=IncidentStatus.MITIGATING,  # Test from MITIGATING (Mitigating), not MITIGATED
        )

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that CLOSED and POST_MORTEM are not in the choices from MITIGATING status
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED not in status_choices
        assert IncidentStatus.POST_MORTEM not in status_choices, "P1/P2 should not be able to go to post-mortem from Mitigating"

    def test_p3_can_skip_from_investigating_to_closed(self):
        """P3+ incidents can go directly from Investigating to Closed."""
        # Get existing P3+ priority that doesn't need post-mortem
        p3_priority = Priority.objects.filter(
            value__gte=3, needs_postmortem=False
        ).first()

        if not p3_priority:
            pytest.skip("No P3+ priority with needs_postmortem=False found in database")

        # Create an incident with P3+ priority in INVESTIGATING status
        incident = IncidentFactory.create(
            priority=p3_priority,
            _status=IncidentStatus.INVESTIGATING,  # Test from INVESTIGATING
        )

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that CLOSED is in the choices from INVESTIGATING status for P3+ but POST_MORTEM is NOT
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED in status_choices
        assert IncidentStatus.POST_MORTEM not in status_choices, "P3+ incidents should not have post-mortem status available"

    def test_p1_p2_can_go_from_mitigated_to_postmortem(self):
        """P1/P2 incidents can go from Mitigated to Post-mortem."""

        # Get existing P1 or P2 priority that needs post-mortem
        p1_priority = Priority.objects.filter(
            value__in=[1, 2], needs_postmortem=True
        ).first()

        if not p1_priority:
            pytest.skip("No P1/P2 priority with needs_postmortem=True found in database")

        # Get PRD environment
        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found in database")

        # Create an incident with P1/P2 priority in Mitigated status with PRD env
        incident = IncidentFactory.create(
            priority=p1_priority,
            environment=prd_env,
            _status=IncidentStatus.MITIGATED,  # MITIGATED = "Mitigated"
        )

        # Create form with the incident
        form = UpdateStatusForm(incident=incident)

        # Check that POST_MORTEM is available but CLOSED is not
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.POST_MORTEM in status_choices, "P1/P2 should be able to go to Post-mortem from Mitigated"
        assert IncidentStatus.CLOSED not in status_choices, "P1/P2 should NOT be able to skip Post-mortem"

    def test_complete_workflow_transitions_p3_plus(self):
        """Test the correct workflow for P3+: can close with reason from early statuses, normal close from Mitigated."""
        # Get P3+ priority
        p3_priority = Priority.objects.filter(
            value__gte=3, needs_postmortem=False
        ).first()

        if not p3_priority:
            pytest.skip("No P3+ priority found")

        # Test workflow for P3+
        test_cases = [
            (IncidentStatus.OPEN, True),           # Can close with reason
            (IncidentStatus.INVESTIGATING, True),  # Can close with reason
            (IncidentStatus.MITIGATING, False),        # Cannot close from Mitigating (must go to Mitigated first)
            (IncidentStatus.MITIGATED, True),          # Can close normally from Mitigated
        ]

        for current_status, should_have_closed in test_cases:
            incident = IncidentFactory.create(
                priority=p3_priority,
                _status=current_status,
            )

            form = UpdateStatusForm(incident=incident)
            status_choices = dict(form.fields["status"].choices)

            if should_have_closed:
                assert IncidentStatus.CLOSED in status_choices, f"P3+ should be able to go to Closed from {current_status.label}"
            else:
                assert IncidentStatus.CLOSED not in status_choices, f"P3+ should NOT be able to go to Closed from {current_status.label}"

            # P3+ should NEVER have post-mortem available
            assert IncidentStatus.POST_MORTEM not in status_choices, f"P3+ should NEVER have post-mortem available from {current_status.label}"

    def test_closure_reason_required_from_early_statuses(self):
        """Test that closure reason is required when closing from Opened or Investigating."""
        # Test for both P1/P2 and P3+ priorities
        priorities = [
            Priority.objects.filter(value__in=[1, 2]).first(),  # P1/P2
            Priority.objects.filter(value__gte=3).first(),       # P3+
        ]

        for priority in priorities:
            if not priority:
                continue

            # Test from Opened and Investigating
            for status in [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]:
                incident = IncidentFactory.create(
                    priority=priority,
                    _status=status,
                )

                # Check that requires_closure_reason returns True
                assert UpdateStatusForm.requires_closure_reason(
                    incident, IncidentStatus.CLOSED
                ), f"Should require closure reason from {status.label} for {priority.name}"

            # Test from other statuses - should NOT require reason
            for status in [IncidentStatus.MITIGATING, IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM]:
                incident = IncidentFactory.create(
                    priority=priority,
                    _status=status,
                )

                # Check that requires_closure_reason returns False
                assert not UpdateStatusForm.requires_closure_reason(
                    incident, IncidentStatus.CLOSED
                ), f"Should NOT require closure reason from {status.label} for {priority.name}"

    def test_cannot_close_from_mitigating(self):
        """Test that incidents cannot be closed directly from Mitigating status."""
        # Test for all priority levels
        priorities = Priority.objects.all()

        for priority in priorities:
            incident = IncidentFactory.create(
                priority=priority,
                _status=IncidentStatus.MITIGATING,  # Mitigating status
            )

            form = UpdateStatusForm(incident=incident)
            status_choices = dict(form.fields["status"].choices)

            # Should NOT have Closed option from Mitigating
            assert IncidentStatus.CLOSED not in status_choices, f"Should NOT be able to close from Mitigating for {priority.name}"

            # Should have Post-mortem option only for P1/P2 priorities that need postmortem
            if priority.needs_postmortem:
                # For P1/P2, should still NOT have post-mortem from MITIGATING (Mitigating)
                assert IncidentStatus.POST_MORTEM not in status_choices, f"P1/P2 should NOT be able to go to Post-mortem from Mitigating for {priority.name}"
            else:
                # For P3+, should not have post-mortem at all
                assert IncidentStatus.POST_MORTEM not in status_choices, f"P3+ should not have post-mortem available for {priority.name}"

    def test_no_incident_shows_all_statuses(self):
        """When no incident is provided, all statuses should be available."""
        # Create form without incident
        form = UpdateStatusForm()

        # Check that all statuses including CLOSED are in the choices
        status_choices = dict(form.fields["status"].choices)
        assert IncidentStatus.CLOSED in status_choices
        assert IncidentStatus.POST_MORTEM in status_choices

    def test_requires_closure_reason_non_closed_status(self):
        """Test requires_closure_reason with non-CLOSED target status."""
        incident = IncidentFactory.create(_status=IncidentStatus.OPEN)

        # Should not require reason for non-CLOSED statuses
        assert not UpdateStatusForm.requires_closure_reason(incident, IncidentStatus.INVESTIGATING)
        assert not UpdateStatusForm.requires_closure_reason(incident, IncidentStatus.MITIGATING)
        assert not UpdateStatusForm.requires_closure_reason(incident, IncidentStatus.MITIGATED)
        assert not UpdateStatusForm.requires_closure_reason(incident, IncidentStatus.POST_MORTEM)

    def test_incident_status_edge_cases(self):
        """Test edge cases for incident status transitions."""
        # Test with incident in default fallback case
        p1_priority = Priority.objects.filter(
            value__in=[1, 2], needs_postmortem=True
        ).first()

        if not p1_priority:
            pytest.skip("No P1/P2 priority found")

        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found")

        # Create incident with an undefined status (should hit default case)
        incident = IncidentFactory.create(
            priority=p1_priority,
            environment=prd_env,
            _status=IncidentStatus.CLOSED  # Already closed
        )

        form = UpdateStatusForm(incident=incident)
        status_choices = dict(form.fields["status"].choices)

        # Should use default choices_lte for unknown/closed status
        assert IncidentStatus.CLOSED in status_choices
