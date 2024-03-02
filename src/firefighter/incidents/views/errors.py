"""From Django default errors views.
https://github.com/django/django/blob/0dd29209091280ccf34e07c9468746c396b7778e/django/views/defaults.py.
"""

from __future__ import annotations

import logging
from typing import Final
from urllib.parse import quote

from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.template import Context, Engine, TemplateDoesNotExist, loader
from django.views.decorators.csrf import requires_csrf_token

logger = logging.getLogger(__name__)

JSON_CONTENT_TYPE: Final[str] = "application/json"


class JsonHttpResponseNotFound(JsonResponse, HttpResponseNotFound):
    pass


class JsonHttpResponseServerError(JsonResponse, HttpResponseServerError):
    pass


class JsonHttpResponseForbidden(JsonResponse, HttpResponseForbidden):
    pass


class JsonHttpResponseBadRequest(JsonResponse, HttpResponseBadRequest):
    pass


ERROR_404_TEMPLATE_NAME = ERROR_403_TEMPLATE_NAME = ERROR_400_TEMPLATE_NAME = (
    ERROR_500_TEMPLATE_NAME
) = "incidents/errors/base.html"

BACKUP_ERROR_PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <title>%(title)s</title>
</head>
<body>
  <h1>%(title)s</h1><p>%(details)s</p>
</body>
</html>
"""


# These views can be called when CsrfViewMiddleware.process_view() not run,
# therefore need @requires_csrf_token in case the template needs
# {% csrf_token %}.


@requires_csrf_token
def page_not_found(
    request: HttpRequest,
    exception: Exception,
    template_name: str = ERROR_404_TEMPLATE_NAME,
) -> HttpResponse:
    """Default 404 handler.

    Templates: :template:`404.html`
    Context:
        request_path
            The path of the requested URL (e.g., '/app/pages/bad_page/'). It's
            quoted to prevent a content injection attack.
        exception
            The message from the exception which triggered the 404 (if one was
            supplied), or the exception class name
    """
    if (
        request.headers.get("Accept", "") == JSON_CONTENT_TYPE
        or request.headers.get("Content-Type", "") == JSON_CONTENT_TYPE
    ):
        return JsonHttpResponseNotFound({
            "error": {"app_code": "NOT_FOUND", "message": "Page not found"}
        })
    exception_repr = exception.__class__.__name__
    # Try to get an "interesting" exception message, if any (and not the ugly
    # Resolver404 dictionary)
    try:
        message = exception.args[0] if exception.args else ""
    except (AttributeError, IndexError):
        logger.exception("Error in page_not_found")
    else:
        if isinstance(message, str):
            exception_repr = message
    context = {
        "request_path": quote(request.path),
        "exception": exception_repr,
        "page_title": "Page not found",
        "title": "Page not found",
        "code": "404",
        "message": "Please check the URL in the address bar and try again.",
    }

    try:
        template = loader.get_template(template_name)
        body = template.render(context, request)
    except TemplateDoesNotExist:
        if template_name != ERROR_404_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        # Render template (even though there are no substitutions) to allow
        # inspecting the context in tests.
        template_backup = Engine().from_string(
            BACKUP_ERROR_PAGE_TEMPLATE
            % {
                "title": "Not Found",
                "details": "The requested resource was not found on this server.",
            },
        )

        body = template_backup.render(Context(context))
    return HttpResponseNotFound(body)


@requires_csrf_token
def server_error(
    request: HttpRequest, template_name: str = ERROR_500_TEMPLATE_NAME
) -> HttpResponse:
    """500 error handler.

    Templates: :template:`500.html`
    Context: None
    """
    context = {
        "page_title": "Server error",
        "title": "Server error",
        "code": "500",
        "message": "Please try again later. This issue has been logged, but feel free to raise the issue.",
        "APP_DISPLAY_NAME": settings.APP_DISPLAY_NAME,
    }
    if (
        request.headers.get("Accept", "") == JSON_CONTENT_TYPE
        or request.headers.get("Content-Type", "") == JSON_CONTENT_TYPE
    ):
        return JsonHttpResponseServerError({
            "error": {"app_code": "SERVER_ERROR", "message": "Server error"}
        })
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_500_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseServerError(
            BACKUP_ERROR_PAGE_TEMPLATE % {"title": "Server Error (500)", "details": ""},
        )
    return HttpResponseServerError(template.render(context))


# pylint: disable=unused-argument
@requires_csrf_token
def bad_request(
    request: HttpRequest,
    exception: Exception,
    template_name: str = ERROR_400_TEMPLATE_NAME,
) -> HttpResponse:
    """400 error handler.

    Templates: :template:`400.html`
    Context: None
    """
    if (
        request.headers.get("Accept", "") == JSON_CONTENT_TYPE
        or request.headers.get("Content-Type", "") == JSON_CONTENT_TYPE
    ):
        return JsonHttpResponseBadRequest({
            "error": {"app_code": "BAD_REQUEST", "message": "Bad request"}
        })
    context = {
        "request_path": quote(request.path),
        "page_title": "Bad request",
        "APP_DISPLAY_NAME": settings.APP_DISPLAY_NAME,
        "title": "Bad request",
        "code": "400",
        "message": "Please check the URL in the address bar and try again.",
    }
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_400_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseBadRequest(
            BACKUP_ERROR_PAGE_TEMPLATE % {"title": "Bad Request (400)", "details": ""},
        )
    # No exception content is passed to the template, to not disclose any
    # sensitive information.
    return HttpResponseBadRequest(template.render(context))


@requires_csrf_token
def permission_denied(
    request: HttpRequest,
    exception: Exception,
    template_name: str = ERROR_403_TEMPLATE_NAME,
) -> HttpResponse:
    """Permission denied (403) handler.

    Templates: :template:`403.html`
    Context:
        exception
            The message from the exception which triggered the 403 (if one was
            supplied).

    If the template does not exist, an HTTP 403 response containing the text
    "403 Forbidden" (as per RFC 7231) will be returned.
    """
    if (
        request.headers.get("Accept", "") == JSON_CONTENT_TYPE
        or request.headers.get("Content-Type", "") == JSON_CONTENT_TYPE
    ):
        return JsonHttpResponseForbidden({
            "error": {"app_code": "FORBIDDEN", "message": "Forbidden"}
        })
    context = {
        "request_path": quote(request.path),
        "exception": str(exception),
        "page_title": "Forbidden",
        "title": "Forbidden",
        "code": "403",
        "message": "You do not have permission to access this page.",
    }
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_403_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseForbidden(
            BACKUP_ERROR_PAGE_TEMPLATE % {"title": "403 Forbidden", "details": ""},
        )
    return HttpResponseForbidden(template.render(request=request, context=context))
