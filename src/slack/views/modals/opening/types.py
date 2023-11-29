from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    import uuid

    from incidents.models.impact import ImpactLevel
    from incidents.models.priority import Priority


class NormalIncidentTypes(StrEnum):
    # XXX Use something better than two ENums and a dict...
    # (Enum of tuple (VALUE, LABEL) or Enum of tuple (VALUE, LABEL, FORM_CLASS) / NamedTuple
    CUSTOMER = "CUSTOMER"
    SELLER = "SELLER"
    INTERNAL = "INTERNAL"
    DOCUMENTATION_REQUEST = "DOCUMENTATION_REQUEST"
    FEATURE_REQUEST = "FEATURE_REQUEST"


ResponseType = Literal["critical", "normal"]


class OpeningData(TypedDict, total=False):
    incident_type: NormalIncidentTypes | None
    response_type: ResponseType | None
    impact_form_data: dict[str, ImpactLevel] | None
    details_form_data: dict[str, Any] | None
    priority: uuid.UUID | None | Priority | str
