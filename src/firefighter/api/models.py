from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self, cast

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta
from rest_framework.authtoken.models import Token

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence


class APIToken(Token):
    class Meta(TypedModelMeta):
        default_permissions: ClassVar[Sequence[str]] = []
        proxy = True


class APITokenProxy(APIToken):
    """Proxy mapping pk to user pk for use in admin.

    Overrides default permissions.
    """

    @property
    def pk(self: Self) -> uuid.UUID:
        return cast("uuid.UUID", self.user_id)  # pyright: ignore[reportGeneralTypeIssues]

    class Meta(TypedModelMeta):
        permissions = [
            ("can_edit_any", "Can reassign token to any user"),
            ("can_add_any", "Can add token to any user"),
            ("can_view_any", "Can view token of all users"),
            ("can_delete_any", "Can delete token of any user"),
            ("can_add_own", "Can add own tokens"),
            ("can_view_own", "Can view own tokens"),
            ("can_delete_own", "Can delete own tokens"),
        ]
        default_permissions: ClassVar[Sequence[str]] = []
        proxy = "rest_framework.authtoken" in settings.INSTALLED_APPS
        abstract = "rest_framework.authtoken" not in settings.INSTALLED_APPS
        verbose_name = _("API Token")
        verbose_name_plural = _("API Tokens")
