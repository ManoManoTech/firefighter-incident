from __future__ import annotations

import logging
from typing import Any

from django_components import component

logger = logging.getLogger(__name__)


@component.register("modal")
class Modal(component.Component):
    template_name = "modal/modal.html"

    def get_context_data(
        self, *args: Any, autoplay: bool = False, **kwargs: Any
    ) -> dict[str, bool]:
        return {
            "autoplay": autoplay,
        }
