from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    import uuid

    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.priority import Priority


ResponseType = Literal["critical", "normal"]


class OpeningData(TypedDict, total=False):
    incident_type: str | None
    response_type: ResponseType | None
    impact_form_data: dict[str, ImpactLevel] | None
    details_form_data: dict[str, Any] | None
    priority: uuid.UUID | Priority | str | None
