from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, TokenAuthentication

if TYPE_CHECKING:
    from django.db.models import Model
    from rest_framework.request import Request

    from firefighter.incidents.models.user import User


class BearerTokenAuthentication(TokenAuthentication):
    """To use `Authorization: Bearer <token>` instead of `Authorization: Token <token>`."""

    keyword = "Bearer"

    def get_model(self) -> type[Model]:
        from firefighter.api.models import APIToken

        return APIToken


class QueryStringSecretAuthentication(BaseAuthentication):
    """Authenticate a request via a `?secret=<value>` query parameter.

    For third parties that cannot send an `Authorization` header (e.g. Jira
    webhooks). The expected value is read from the Django setting referenced
    by `setting_name`, populated from an env var fed by Vault.

    Subclasses must set:
      - `setting_name`: name of the Django setting holding the expected value
      - `service_username`: username of the Django user to bind to `request.user`
    """

    setting_name: str = ""
    service_username: str = ""

    def authenticate(self, request: Request) -> tuple[User, None] | None:
        provided = request.query_params.get("secret")
        if not provided:
            return None

        expected = getattr(settings, self.setting_name, None)
        if not expected or not secrets.compare_digest(str(provided), str(expected)):
            raise exceptions.AuthenticationFailed("Invalid webhook secret.")

        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=self.service_username)
        except user_model.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed(
                "Webhook service user is not provisioned."
            ) from exc

        if not user.is_active:
            raise exceptions.AuthenticationFailed("Webhook service user is inactive.")

        return (user, None)

    def authenticate_header(self, _request: Request) -> str:
        return 'QueryString realm="webhook"'


class JiraWebhookSecretAuthentication(QueryStringSecretAuthentication):
    """Authenticate Jira webhook callers via `?secret=<value>`.

    The expected value is compared (constant time) against
    `settings.RAID_JIRA_WEBHOOK_SECRET`. On success the request is bound to
    the dedicated `jira-webhook` service user.
    """

    setting_name = "RAID_JIRA_WEBHOOK_SECRET"
    service_username = "jira-webhook"
