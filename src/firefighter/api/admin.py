from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from rest_framework.authtoken.admin import TokenAdmin
from rest_framework.authtoken.models import TokenProxy

from firefighter.api.models import APITokenProxy
from firefighter.firefighter.admin import admin_custom as admin
from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from django.db.models import ForeignKey
    from django.db.models.query import QuerySet
    from django.forms import ModelChoiceField, ModelForm
    from django.http.request import HttpRequest as BaseHttpRequest

    class HttpRequest(BaseHttpRequest):
        user: User


class APITokenAdmin(TokenAdmin):
    """Custom Admin for DRF Token.
    Add supports for custom permissions.
    """

    def formfield_for_foreignkey(
        self,
        db_field: ForeignKey[Any, Any],
        request: HttpRequest,  # type: ignore[override]
        **kwargs: Any,
    ) -> ModelChoiceField:  # type: ignore[type-arg]
        """Show all or only current user depending on permissions."""
        if db_field.name == "user":
            if request.user.has_perm("api.can_add_any") or request.user.has_perm(
                "api.can_edit_any"
            ):
                kwargs["queryset"] = User.objects.all()
            elif request.user.has_perm("api.can_add_own"):
                kwargs["queryset"] = User.objects.filter(id=request.user.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)  # type: ignore[return-value]

    def get_form(
        self,
        request: HttpRequest,  # type: ignore[override]
        obj: APITokenProxy | None = None,
        change: bool = False,  # noqa: FBT001, FBT002
        **kwargs: Any,
    ) -> type[ModelForm[APITokenProxy]]:
        """Prefill the form with the current user."""
        form: type[ModelForm[APITokenProxy]] = super().get_form(
            request, obj, change, **kwargs
        )
        form.base_fields["user"].initial = request.user
        return form

    def get_queryset(self, request: HttpRequest) -> QuerySet[APITokenProxy]:  # type: ignore[override]
        """Show all or only own tokens depending on permissions."""
        qs = super().get_queryset(request)
        if request.user.has_perm("api.can_view_any"):
            return qs
        return qs.filter(user=request.user)

    def get_sortable_by(self, request: HttpRequest):  # type: ignore[no-untyped-def,override]
        """Hack to send a message depending on the status of the user."""
        if request.user.has_perm("api.can_view_any"):
            self.message_user(request, "You are seeing all tokens.", messages.WARNING)
        elif request.user.has_perm("api.can_view_own"):
            self.message_user(
                request, "You are only seeing your tokens.", messages.WARNING
            )
        return super().get_sortable_by(request)

    def has_view_permission(
        self,
        request: HttpRequest,  # type: ignore[override]
        obj: APITokenProxy | None = None,
    ) -> bool:
        if obj is None:
            return request.user.has_perm("api.can_view_any") or request.user.has_perm(
                "api.can_view_own"
            )
        if request.user.has_perm("api.can_view_any"):
            return True
        if request.user.has_perm("api.can_view_own"):
            return bool(obj.user == request.user)
        return False

    def has_add_permission(self, request: HttpRequest) -> bool:  # type: ignore[override]
        return request.user.has_perm("api.can_add_any") or request.user.has_perm(
            "api.can_add_own"
        )

    def has_delete_permission(
        self,
        request: HttpRequest,  # type: ignore[override]
        obj: APITokenProxy | None = None,
    ) -> bool:
        if obj is None:
            return request.user.has_perm("api.can_delete_any") or request.user.has_perm(
                "api.can_delete_own"
            )
        if request.user.has_perm("api.can_delete_any"):
            return True
        if request.user.has_perm("api.can_delete_own"):
            return bool(obj.user == request.user)
        return False

    def has_change_permission(
        self,
        request: HttpRequest,  # type: ignore[override]
        _obj: APITokenProxy | None = None,
    ) -> bool:
        return request.user.has_perm("api.can_edit_any")


# Remove the default TokenAdmin created by DRF and replace it with our custom one.
admin.site.unregister(TokenProxy)
admin.site.register(APITokenProxy, APITokenAdmin)
