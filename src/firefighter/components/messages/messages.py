from __future__ import annotations

import logging
from typing import Any

from django_components import component

logger = logging.getLogger(__name__)


@component.register("messages")
class Messages(component.Component):
    template_name = "messages/messages.html"

    def get_context_data(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return kwargs
