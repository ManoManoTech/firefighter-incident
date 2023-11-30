from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_components import component

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


@component.register("avatar")
class Avatar(component.Component):
    template_name = "avatar/avatar.html"

    def get_context_data(self, user: User, *args: Any, **kwargs: Any) -> dict[str, Any]:
        size_px, size_tailwind = (40, 10) if kwargs.get("size") == "md" else (80, 20)
        return {"user": user, "size_tailwind": size_tailwind, "size_px": size_px}
