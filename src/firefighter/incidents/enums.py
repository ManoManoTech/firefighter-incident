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
