from __future__ import annotations

import logging
from typing import Any

from django_components import component

logger = logging.getLogger(__name__)


@component.register("card")
class Card(component.Component):
    template_name = "card/card.html"

    def get_context_data(self, *args: Any, **kwargs: dict[str, Any]) -> dict[str, Any]:
        return kwargs
