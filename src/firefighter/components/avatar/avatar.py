from __future__ import annotations

import logging
from typing import Any, NotRequired, Required, TypedDict

from django_components import component

from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


class Data(TypedDict):
    user: User
    size_tailwind: int
    size_px: int


Args = tuple[User]


class Kwargs(TypedDict, total=False):
    user: Required[User]
    size: NotRequired[str]


@component.register("avatar")
class Avatar(component.Component):
    template_name = "avatar/avatar.html"

    def get_context_data(self, user: User, **kwargs: Any) -> Data:
        size_px, size_tailwind = (40, 10) if kwargs.get("size") == "md" else (80, 20)
        return {
            "user": user,
            "size_tailwind": size_tailwind,
            "size_px": size_px,
        }
