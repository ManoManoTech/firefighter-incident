from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from firefighter.slack.views import handler

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


@method_decorator(csrf_exempt, name="dispatch")
class SlackEventsHandler(View):
    """Handle all Slack events."""

    @classmethod
    def post(cls, request: HttpRequest) -> HttpResponse:
        return handler.handle(request)
