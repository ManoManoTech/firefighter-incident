from __future__ import annotations

from django.db import models


class IncidentStatus(models.IntegerChoices):
    OPEN = 10, "Open"
    INVESTIGATING = 20, "Investigating"
    MITIGATING = 30, "Mitigating"
    MITIGATED = 40, "Mitigated"
    POST_MORTEM = 50, "Post-mortem"
    CLOSED = 60, "Closed"
    # Closed as not a real incident (duplicate, false alarm...). Terminal like CLOSED,
    # and after it so that "status < CLOSED" keeps meaning "still open".
    REJECTED = 70, "Rejected"

    @property
    def is_terminal(self) -> bool:
        """Closed or rejected: nothing happens to the incident any more."""
        return self.value >= IncidentStatus.CLOSED.value

    @staticmethod
    def lt(val: int) -> list[IncidentStatus]:
        return [i for i in IncidentStatus if i.value < val]

    @staticmethod
    def lte(val: int) -> list[IncidentStatus]:
        return [i for i in IncidentStatus if i.value <= val]

    @staticmethod
    def gt(val: int) -> list[IncidentStatus]:
        return [i for i in IncidentStatus if i.value > val]

    @staticmethod
    def gte(val: int) -> list[IncidentStatus]:
        return [i for i in IncidentStatus if i.value >= val]

    @staticmethod
    def choices_lt(val: int) -> list[tuple[int, str]]:
        return [i for i in IncidentStatus.choices if i[0] < val]

    @staticmethod
    def choices_lte(val: int) -> list[tuple[int, str]]:
        return [i for i in IncidentStatus.choices if i[0] <= val]

    @staticmethod
    def choices_lte_skip_postmortem(val: int) -> list[tuple[int, str]]:
        """Return choices up to val but excluding POST_MORTEM (for P3+ incidents)."""
        return [i for i in IncidentStatus.choices if i[0] <= val and i[0] != IncidentStatus.POST_MORTEM]


class ClosureReason(models.TextChoices):
    """Reasons for direct incident closure bypassing normal workflow."""

    RESOLVED = "resolved", "Resolved normally"
    DUPLICATE = "duplicate", "Duplicate incident"
    FALSE_POSITIVE = "false_positive", "False alarm - no actual issue"
    SUPERSEDED = "superseded", "Superseded by another incident"
    # Deprecated: a third-party cause is now recorded as the incident origin
    # (IncidentOrigin.PARTNER) on a real incident. Kept for historical rows only.
    EXTERNAL = "external", "External dependency/known issue"
    CANCELLED = "cancelled", "Cancelled - no longer relevant"


REJECTION_CLOSURE_REASONS: frozenset[ClosureReason] = frozenset({
    ClosureReason.DUPLICATE,
    ClosureReason.FALSE_POSITIVE,
    ClosureReason.SUPERSEDED,
    ClosureReason.CANCELLED,
})
"""Closure reasons meaning the incident was not a real one: it ends REJECTED."""

OFFERED_CLOSURE_REASONS: tuple[ClosureReason, ...] = (
    ClosureReason.RESOLVED,
    ClosureReason.DUPLICATE,
    ClosureReason.FALSE_POSITIVE,
    ClosureReason.SUPERSEDED,
    ClosureReason.CANCELLED,
)
"""Closure reasons a user can pick: EXTERNAL is replaced by the incident origin."""


def status_for_closure_reason(reason: str | None) -> IncidentStatus:
    """Terminal status of an incident closed with this reason."""
    if reason in REJECTION_CLOSURE_REASONS:
        return IncidentStatus.REJECTED
    return IncidentStatus.CLOSED


class IncidentOrigin(models.TextChoices):
    """Where an incident comes from, independently of how it ended."""

    INTERNAL = "internal", "Internal"
    PARTNER = "partner", "Partner (third party)"


DOWNGRADE_WORKFLOW_EVENT_TYPE = "downgrade_workflow"
"""`IncidentUpdate.event_type` of the closure made by switching to the Jira-ticket workflow.

The incident channel is closed but the incident goes on, on its Jira ticket: integrations
must not treat this closure as the end of the incident.
"""
