from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

FF_USER_ID_HEADER: str = settings.FF_USER_ID_HEADER

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


class HeaderUser:
    """Adds the user ID to the response headers configured with "FF-User-Id", to log in access logs."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        request_user_id = request.user.id if request.user.is_authenticated else None

        response: HttpResponse = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.
        if request_user_id:
            response.headers[FF_USER_ID_HEADER] = str(request_user_id)

        return response
