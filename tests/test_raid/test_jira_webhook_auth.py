"""Tests for the X-Hub-Signature HMAC authentication on Jira webhook endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from unittest.mock import patch

import pytest
from rest_framework import exceptions, status
from rest_framework.request import Request as DRFRequest
from rest_framework.test import APIClient, APIRequestFactory

from firefighter.api.authentication import JiraHmacWebhookAuthentication

JIRA_UPDATE_URL = "/api/v2/firefighter/raid/jira_update"
JIRA_COMMENT_URL = "/api/v2/firefighter/raid/jira_comment"
SECRET = secrets.token_urlsafe(32)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def _configure_secret(settings):
    settings.RAID_JIRA_WEBHOOK_SECRET = SECRET


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.mark.usefixtures("_configure_secret")
class TestJiraUpdateWebhookAuth:
    def test_missing_header_returns_401(self, api_client):
        response = api_client.post(JIRA_UPDATE_URL, data={}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["errors"][0]["code"] == "not_authenticated"

    def test_wrong_signature_returns_401(self, api_client):
        response = api_client.post(
            JIRA_UPDATE_URL,
            data={},
            format="json",
            HTTP_X_HUB_SIGNATURE="sha256=" + "0" * 64,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_malformed_header_returns_401(self, api_client):
        response = api_client.post(
            JIRA_UPDATE_URL,
            data={},
            format="json",
            HTTP_X_HUB_SIGNATURE="not-a-valid-format",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unsupported_method_returns_401(self, api_client):
        body = json.dumps({}).encode()
        response = api_client.post(
            JIRA_UPDATE_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE="md5=" + "a" * 32,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_query_string_secret_still_returns_401(self, api_client):
        """Regression: the old ?secret= scheme is no longer accepted."""
        response = api_client.post(
            f"{JIRA_UPDATE_URL}?secret={SECRET}", data={}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["errors"][0]["code"] == "not_authenticated"

    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.save")
    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.is_valid")
    def test_valid_signature_passes_auth(
        self, mock_is_valid, mock_save, api_client
    ):
        mock_is_valid.return_value = True
        mock_save.return_value = None
        body = json.dumps({"webhookEvent": "jira:issue_updated"}).encode()
        signature = _sign(SECRET, body)
        response = api_client.post(
            JIRA_UPDATE_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE=f"sha256={signature}",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_is_valid.assert_called_once_with(raise_exception=True)
        mock_save.assert_called_once()

    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.save")
    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.is_valid")
    def test_signature_method_is_case_insensitive(
        self, mock_is_valid, mock_save, api_client
    ):
        mock_is_valid.return_value = True
        mock_save.return_value = None
        body = json.dumps({}).encode()
        signature = _sign(SECRET, body)
        response = api_client.post(
            JIRA_UPDATE_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE=f"SHA256={signature}",
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestJiraUpdateWebhookAuthUnconfigured:
    def test_unconfigured_secret_returns_401(self, api_client, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = ""
        response = api_client.post(
            JIRA_UPDATE_URL,
            data=b"{}",
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE="sha256=" + "f" * 64,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.usefixtures("_configure_secret")
class TestJiraCommentWebhookAuth:
    def test_missing_header_returns_401(self, api_client):
        response = api_client.post(JIRA_COMMENT_URL, data={}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_wrong_signature_returns_401(self, api_client):
        response = api_client.post(
            JIRA_COMMENT_URL,
            data={},
            format="json",
            HTTP_X_HUB_SIGNATURE="sha256=" + "0" * 64,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("firefighter.raid.serializers.JiraWebhookCommentSerializer.save")
    @patch("firefighter.raid.serializers.JiraWebhookCommentSerializer.is_valid")
    def test_valid_signature_passes_auth(
        self, mock_is_valid, mock_save, api_client
    ):
        mock_is_valid.return_value = True
        mock_save.return_value = None
        body = json.dumps({"webhookEvent": "comment_created"}).encode()
        signature = _sign(SECRET, body)
        response = api_client.post(
            JIRA_COMMENT_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE=f"sha256={signature}",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_is_valid.assert_called_once_with(raise_exception=True)
        mock_save.assert_called_once()


@pytest.mark.django_db
class TestJiraWebhookServiceUser:
    def test_service_user_exists_and_is_a_bot(self):
        """The data migration must have provisioned the jira-webhook user."""
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(username="jira-webhook")
        assert user.is_active
        assert user.bot
        assert not user.is_staff
        assert not user.is_superuser

    def test_authenticate_binds_request_to_service_user(self, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = SECRET
        body = b'{"hello":"world"}'
        sig = _sign(SECRET, body)
        factory = APIRequestFactory()
        request = DRFRequest(
            factory.post(
                "/whatever",
                data=body,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE=f"sha256={sig}",
            )
        )

        user, auth = JiraHmacWebhookAuthentication().authenticate(request)

        assert user.username == "jira-webhook"
        assert auth is None

    def test_authenticate_raises_on_inactive_user(self, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = SECRET
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_model.objects.filter(username="jira-webhook").update(is_active=False)
        body = b"{}"
        sig = _sign(SECRET, body)
        try:
            factory = APIRequestFactory()
            request = DRFRequest(
                factory.post(
                    "/whatever",
                    data=body,
                    content_type="application/json",
                    HTTP_X_HUB_SIGNATURE=f"sha256={sig}",
                )
            )

            with pytest.raises(exceptions.AuthenticationFailed):
                JiraHmacWebhookAuthentication().authenticate(request)
        finally:
            user_model.objects.filter(username="jira-webhook").update(is_active=True)

    def test_authenticate_returns_none_without_header(self, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = SECRET
        factory = APIRequestFactory()
        request = DRFRequest(factory.post("/whatever"))

        result = JiraHmacWebhookAuthentication().authenticate(request)

        assert result is None
