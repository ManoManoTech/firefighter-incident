from __future__ import annotations

import logging
from typing import Any, NotRequired, Required, TypedDict, Unpack

from django_components import EmptyTuple, component

logger = logging.getLogger(__name__)


class Data(TypedDict, total=False):
    id: Required[str]
    card_title: NotRequired[str]


@component.register("card")
class Card(component.Component[EmptyTuple, Data, Data, Any]):  # type: ignore[type-var]
    template_name = "card/card.html"

    def get_context_data(self, *args: Any, **kwargs: Unpack[Data]) -> Data:
        return kwargs
