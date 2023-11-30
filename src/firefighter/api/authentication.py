from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.authentication import TokenAuthentication

if TYPE_CHECKING:
    from django.db.models import Model


class BearerTokenAuthentication(TokenAuthentication):
    """To use `Authorization: Bearer <token>` instead of `Authorization: Token <token>`."""

    keyword = "Bearer"

    def get_model(self) -> type[Model]:
        # ruff: noqa: PLC0415
        from firefighter.api.models import APIToken

        return APIToken
