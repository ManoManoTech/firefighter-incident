from __future__ import annotations

from django.db import models


class IncidentStatus(models.IntegerChoices):
    OPEN = 10, "Open"
    INVESTIGATING = 20, "Investigating"
    FIXING = 30, "Mitigating"
    FIXED = 40, "Mitigated"
    POST_MORTEM = 50, "Post-mortem"
    CLOSED = 60, "Closed"

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


class ClosureReason(models.TextChoices):
    """Reasons for direct incident closure bypassing normal workflow."""

    RESOLVED = "resolved", "Resolved normally"
    DUPLICATE = "duplicate", "Duplicate incident"
    FALSE_POSITIVE = "false_positive", "False alarm - no actual issue"
    SUPERSEDED = "superseded", "Superseded by another incident"
    EXTERNAL = "external", "External dependency/known issue"
    CANCELLED = "cancelled", "Cancelled - no longer relevant"
