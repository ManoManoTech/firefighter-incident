"""Test complete workflow transitions according to the diagram.

Workflow transitions:

P1/P2:
- OPEN → [INVESTIGATING, CLOSED (avec reason form)]
- INVESTIGATING → [MITIGATING, CLOSED (avec reason form)]
- MITIGATING → [MITIGATED]
- MITIGATED → [POST_MORTEM]
- POST_MORTEM → [CLOSED]

P3/P4/P5:
- OPEN → [INVESTIGATING, CLOSED (avec reason form)]
- INVESTIGATING → [MITIGATING, CLOSED (avec reason form)]
- MITIGATING → [MITIGATED]
- MITIGATED → [CLOSED]
"""
from __future__ import annotations

import pytest
from django.test import TestCase

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.incidents.models import Environment, Priority


@pytest.mark.django_db
class TestCompleteWorkflowTransitions(TestCase):
    """Test that all workflow transitions are implemented correctly."""

    def test_p1_p2_complete_workflow_transitions(self):
        """Test all P1/P2 workflow transitions according to the diagram."""
        # Get P1/P2 priority
        p1_priority = Priority.objects.filter(
            value__in=[1, 2], needs_postmortem=True
        ).first()

        if not p1_priority:
            pytest.skip("No P1/P2 priority found")

        prd_env = Environment.objects.filter(value="PRD").first()
        if not prd_env:
            pytest.skip("No PRD environment found")

        # Test all transitions
        transitions = [
            # Test transitions from each status
            (IncidentStatus.OPEN, [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]),
            (IncidentStatus.INVESTIGATING, [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]),
            (IncidentStatus.MITIGATING, [IncidentStatus.MITIGATED]),
            (IncidentStatus.MITIGATED, [IncidentStatus.POST_MORTEM]),
            (IncidentStatus.POST_MORTEM, [IncidentStatus.CLOSED]),
        ]

        for current_status, expected_statuses in transitions:
            incident = IncidentFactory.create(
                priority=p1_priority,
                environment=prd_env,
                _status=current_status,
            )

            form = UpdateStatusForm(incident=incident)
            status_choices = dict(form.fields["status"].choices)
            available_statuses = list(status_choices.keys())

            # Remove current status from available (can't transition to same status)
            if current_status in available_statuses:
                available_statuses.remove(current_status)

            for expected_status in expected_statuses:
                assert expected_status in available_statuses, (
                    f"P1/P2: From {current_status.label}, should be able to go to {expected_status.label}. "
                    f"Available: {[IncidentStatus(s).label for s in available_statuses]}"
                )

            # Verify no unexpected statuses are available
            unexpected_statuses = set(available_statuses) - set(expected_statuses)
            assert not unexpected_statuses, (
                f"P1/P2: From {current_status.label}, unexpected statuses available: "
                f"{[IncidentStatus(s).label for s in unexpected_statuses]}"
            )

    def test_p3_plus_complete_workflow_transitions(self):
        """Test all P3+ workflow transitions according to the diagram."""
        # Get P3+ priority
        p3_priority = Priority.objects.filter(
            value__gte=3, needs_postmortem=False
        ).first()

        if not p3_priority:
            pytest.skip("No P3+ priority found")

        # Test all transitions
        transitions = [
            # Test transitions from each status
            (IncidentStatus.OPEN, [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED]),
            (IncidentStatus.INVESTIGATING, [IncidentStatus.MITIGATING, IncidentStatus.CLOSED]),
            (IncidentStatus.MITIGATING, [IncidentStatus.MITIGATED]),
            (IncidentStatus.MITIGATED, [IncidentStatus.CLOSED]),
        ]

        for current_status, expected_statuses in transitions:
            incident = IncidentFactory.create(
                priority=p3_priority,
                _status=current_status,
            )

            form = UpdateStatusForm(incident=incident)
            status_choices = dict(form.fields["status"].choices)
            available_statuses = list(status_choices.keys())

            # Remove current status from available (can't transition to same status)
            if current_status in available_statuses:
                available_statuses.remove(current_status)

            for expected_status in expected_statuses:
                assert expected_status in available_statuses, (
                    f"P3+: From {current_status.label}, should be able to go to {expected_status.label}. "
                    f"Available: {[IncidentStatus(s).label for s in available_statuses]}"
                )

            # Verify no unexpected statuses are available (especially POST_MORTEM)
            unexpected_statuses = set(available_statuses) - set(expected_statuses)
            assert not unexpected_statuses, (
                f"P3+: From {current_status.label}, unexpected statuses available: "
                f"{[IncidentStatus(s).label for s in unexpected_statuses]}"
            )

            # Specifically verify POST_MORTEM is never available for P3+
            assert IncidentStatus.POST_MORTEM not in available_statuses, (
                f"P3+: POST_MORTEM should never be available, but found from {current_status.label}"
            )

    def test_closure_reason_requirements(self):
        """Test that closure reason is required only from OPEN and INVESTIGATING."""
        priorities = [
            Priority.objects.filter(value__in=[1, 2]).first(),  # P1/P2
            Priority.objects.filter(value__gte=3).first(),       # P3+
        ]

        for priority in priorities:
            if not priority:
                continue

            # Should require reason from OPEN and INVESTIGATING
            for status in [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]:
                incident = IncidentFactory.create(
                    priority=priority,
                    _status=status,
                )

                assert UpdateStatusForm.requires_closure_reason(
                    incident, IncidentStatus.CLOSED
                ), f"Should require closure reason from {status.label} for {priority.name}"

            # Should NOT require reason from other statuses
            for status in [IncidentStatus.MITIGATING, IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM]:
                incident = IncidentFactory.create(
                    priority=priority,
                    _status=status,
                )

                assert not UpdateStatusForm.requires_closure_reason(
                    incident, IncidentStatus.CLOSED
                ), f"Should NOT require closure reason from {status.label} for {priority.name}"
