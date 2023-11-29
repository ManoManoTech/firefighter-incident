from __future__ import annotations

import logging
from functools import cache
from typing import Any, Generic, Never, TypeVar

from django.core.exceptions import BadRequest, PermissionDenied
from django.db import connection
from django.db.models import Model
from django.db.utils import OperationalError
from django.http import Http404, HttpRequest, JsonResponse
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_safe
from django.views.generic import DetailView

logger = logging.getLogger(__name__)

_MT = TypeVar("_MT", bound=Model)


@require_safe
def healthcheck(request: HttpRequest) -> JsonResponse:
    db_ok = True
    try:
        connection.ensure_connection()
    except OperationalError:
        logger.exception("Healthcheck failed: can't access DB!")
        db_ok = False

    if db_ok:
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "fail"}, status=503)


def permission_denied_view(request: HttpRequest) -> Never:
    raise PermissionDenied("Permission denied")


def not_found_view(request: HttpRequest) -> Never:
    raise Http404("Not found")


def bad_request_view(request: HttpRequest) -> Never:
    raise BadRequest("Unknown parameters")


def server_error_view(request: HttpRequest) -> Never:
    # pylint: disable=broad-exception-raised
    raise Exception("Test exception for 500")  # noqa: TRY002


class CustomDetailView(DetailView[_MT], Generic[_MT]):
    """A custom detail view that adds the admin edit URL to the context, as `admin_edit_url`."""

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        obj: _MT = context[self.get_context_object_name(self.object) or "object"]
        return {**context, "admin_edit_url": get_admin_edit_url(self.model, obj.pk)}


@cache
def get_admin_edit_url(model_class: type[Model], object_pk: Any) -> str | None:
    """Construct the URL name for the admin edit page using the model's app_label and model_name."""
    app_label: str = model_class._meta.app_label  # noqa: SLF001
    model_name = model_class._meta.model_name  # noqa: SLF001
    url_name: str = f"admin:{app_label}_{model_name}_change"

    try:
        return reverse(url_name, args=[object_pk])
    except NoReverseMatch:
        return None
