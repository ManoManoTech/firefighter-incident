from __future__ import annotations

import hashlib
import hmac
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


class JiraHmacWebhookAuthentication(BaseAuthentication):
    """Authenticate Jira webhook callers via the `X-Hub-Signature` header.

    Jira webhooks cannot send custom `Authorization` headers; when a webhook
    has a Secret configured in the Atlassian admin, Jira signs the raw
    request body with HMAC and sends the signature in `X-Hub-Signature`,
    formatted as `method=signature` per the WebSub spec (see
    https://developer.atlassian.com/cloud/jira/platform/webhooks/).

    The expected secret is read from `settings.RAID_JIRA_WEBHOOK_SECRET`
    (fed by Vault). Successful calls are bound to the dedicated
    `jira-webhook` service user provisioned by migration
    `incidents.0033_create_jira_webhook_service_user`.
    """

    setting_name = "RAID_JIRA_WEBHOOK_SECRET"
    service_username = "jira-webhook"
    supported_method = "sha256"

    def authenticate(self, request: Request) -> tuple[User, None] | None:
        header = request.META.get("HTTP_X_HUB_SIGNATURE")
        if not header:
            return None

        expected_secret = getattr(settings, self.setting_name, None)
        if not expected_secret:
            raise exceptions.AuthenticationFailed("Webhook secret not configured.")

        method, _, received_sig = header.partition("=")
        if not received_sig:
            raise exceptions.AuthenticationFailed("Malformed X-Hub-Signature header.")
        if method.lower() != self.supported_method:
            msg = f"Unsupported X-Hub-Signature method: {method!r}"
            raise exceptions.AuthenticationFailed(msg)

        computed_sig = hmac.new(
            expected_secret.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(computed_sig, received_sig):
            raise exceptions.AuthenticationFailed("Invalid webhook signature.")

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
        return 'Signature realm="jira-webhook"'
