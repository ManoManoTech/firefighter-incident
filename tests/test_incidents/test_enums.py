"""Test the incidents enums module."""
from __future__ import annotations

from firefighter.incidents.enums import ClosureReason, IncidentStatus


class TestIncidentStatus:
    """Test IncidentStatus enum and its methods."""

    def test_enum_values(self):
        """Test that enum values are correctly defined."""
        assert IncidentStatus.OPEN.value == 10
        assert IncidentStatus.INVESTIGATING.value == 20
        assert IncidentStatus.MITIGATING.value == 30
        assert IncidentStatus.MITIGATED.value == 40
        assert IncidentStatus.POST_MORTEM.value == 50
        assert IncidentStatus.CLOSED.value == 60

    def test_enum_labels(self):
        """Test that enum labels are correctly defined."""
        assert IncidentStatus.OPEN.label == "Open"
        assert IncidentStatus.INVESTIGATING.label == "Investigating"
        assert IncidentStatus.MITIGATING.label == "Mitigating"
        assert IncidentStatus.MITIGATED.label == "Mitigated"
        assert IncidentStatus.POST_MORTEM.label == "Post-mortem"
        assert IncidentStatus.CLOSED.label == "Closed"

    def test_lt_method(self):
        """Test the lt static method."""
        result = IncidentStatus.lt(30)
        expected = [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]
        assert result == expected

    def test_lte_method(self):
        """Test the lte static method."""
        result = IncidentStatus.lte(30)
        expected = [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATING]
        assert result == expected

    def test_gt_method(self):
        """Test the gt static method."""
        result = IncidentStatus.gt(30)
        expected = [IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM, IncidentStatus.CLOSED]
        assert result == expected

    def test_gte_method(self):
        """Test the gte static method."""
        result = IncidentStatus.gte(30)
        expected = [IncidentStatus.MITIGATING, IncidentStatus.MITIGATED, IncidentStatus.POST_MORTEM, IncidentStatus.CLOSED]
        assert result == expected

    def test_choices_lt_method(self):
        """Test the choices_lt static method."""
        result = IncidentStatus.choices_lt(30)
        expected = [(10, "Open"), (20, "Investigating")]
        assert result == expected

    def test_choices_lte_method(self):
        """Test the choices_lte static method."""
        result = IncidentStatus.choices_lte(30)
        expected = [(10, "Open"), (20, "Investigating"), (30, "Mitigating")]
        assert result == expected

    def test_choices_lte_skip_postmortem_method(self):
        """Test the choices_lte_skip_postmortem static method."""
        result = IncidentStatus.choices_lte_skip_postmortem(60)
        expected = [(10, "Open"), (20, "Investigating"), (30, "Mitigating"), (40, "Mitigated"), (60, "Closed")]
        assert result == expected

        # Test that POST_MORTEM is excluded
        assert (50, "Post-mortem") not in result


class TestClosureReason:
    """Test ClosureReason enum."""

    def test_enum_values(self):
        """Test that closure reason values are correctly defined."""
        assert ClosureReason.RESOLVED.value == "resolved"
        assert ClosureReason.DUPLICATE.value == "duplicate"
        assert ClosureReason.FALSE_POSITIVE.value == "false_positive"
        assert ClosureReason.SUPERSEDED.value == "superseded"
        assert ClosureReason.EXTERNAL.value == "external"
        assert ClosureReason.CANCELLED.value == "cancelled"

    def test_enum_labels(self):
        """Test that closure reason labels are correctly defined."""
        assert ClosureReason.RESOLVED.label == "Resolved normally"
        assert ClosureReason.DUPLICATE.label == "Duplicate incident"
        assert ClosureReason.FALSE_POSITIVE.label == "False alarm - no actual issue"
        assert ClosureReason.SUPERSEDED.label == "Superseded by another incident"
        assert ClosureReason.EXTERNAL.label == "External dependency/known issue"
        assert ClosureReason.CANCELLED.label == "Cancelled - no longer relevant"

    def test_choices_available(self):
        """Test that choices are available."""
        choices = ClosureReason.choices
        assert len(choices) == 6
        assert ("resolved", "Resolved normally") in choices
        assert ("duplicate", "Duplicate incident") in choices
