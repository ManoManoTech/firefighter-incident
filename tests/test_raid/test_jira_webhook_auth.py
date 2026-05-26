"""Tests for the ?secret= authentication on Jira webhook endpoints."""

from __future__ import annotations

import secrets
from unittest.mock import patch

import pytest
from rest_framework import exceptions, status
from rest_framework.request import Request as DRFRequest
from rest_framework.test import APIClient, APIRequestFactory

from firefighter.api.authentication import JiraWebhookSecretAuthentication


def _drf_request(factory: APIRequestFactory, path: str) -> DRFRequest:
    return DRFRequest(factory.post(path))


JIRA_UPDATE_URL = "/api/v2/firefighter/raid/jira_update"
JIRA_COMMENT_URL = "/api/v2/firefighter/raid/jira_comment"
SECRET = secrets.token_urlsafe(32)


@pytest.fixture
def _configure_secret(settings):
    settings.RAID_JIRA_WEBHOOK_SECRET = SECRET


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.mark.usefixtures("_configure_secret")
class TestJiraUpdateWebhookAuth:
    def test_missing_secret_returns_401(self, api_client):
        response = api_client.post(JIRA_UPDATE_URL, data={}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_wrong_secret_returns_401(self, api_client):
        response = api_client.post(
            f"{JIRA_UPDATE_URL}?secret=nope", data={}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bearer_header_returns_401(self, api_client):
        response = api_client.post(
            JIRA_UPDATE_URL,
            data={},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {SECRET}",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.save")
    @patch("firefighter.raid.serializers.JiraWebhookUpdateSerializer.is_valid")
    def test_correct_secret_passes_auth(
        self, mock_is_valid, mock_save, api_client
    ):
        mock_is_valid.return_value = True
        mock_save.return_value = None
        response = api_client.post(
            f"{JIRA_UPDATE_URL}?secret={SECRET}", data={}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_is_valid.assert_called_once_with(raise_exception=True)
        mock_save.assert_called_once()


@pytest.mark.django_db
class TestJiraUpdateWebhookAuthUnconfigured:
    def test_unconfigured_secret_returns_401(self, api_client, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = ""
        response = api_client.post(
            f"{JIRA_UPDATE_URL}?secret=anything", data={}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.usefixtures("_configure_secret")
class TestJiraCommentWebhookAuth:
    def test_missing_secret_returns_401(self, api_client):
        response = api_client.post(JIRA_COMMENT_URL, data={}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_wrong_secret_returns_401(self, api_client):
        response = api_client.post(
            f"{JIRA_COMMENT_URL}?secret=nope", data={}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("firefighter.raid.serializers.JiraWebhookCommentSerializer.save")
    @patch("firefighter.raid.serializers.JiraWebhookCommentSerializer.is_valid")
    def test_correct_secret_passes_auth(
        self, mock_is_valid, mock_save, api_client
    ):
        mock_is_valid.return_value = True
        mock_save.return_value = None
        response = api_client.post(
            f"{JIRA_COMMENT_URL}?secret={SECRET}", data={}, format="json"
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
        request = _drf_request(APIRequestFactory(), f"/whatever?secret={SECRET}")

        user, auth = JiraWebhookSecretAuthentication().authenticate(request)

        assert user.username == "jira-webhook"
        assert auth is None

    def test_authenticate_raises_on_inactive_user(self, settings):
        settings.RAID_JIRA_WEBHOOK_SECRET = SECRET
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_model.objects.filter(username="jira-webhook").update(is_active=False)
        try:
            request = _drf_request(APIRequestFactory(), f"/whatever?secret={SECRET}")

            with pytest.raises(exceptions.AuthenticationFailed):
                JiraWebhookSecretAuthentication().authenticate(request)
        finally:
            user_model.objects.filter(username="jira-webhook").update(is_active=True)

    def test_authenticate_returns_none_without_secret_param(self, settings):
        """No `?secret=` → returns None, letting DRF emit 401 from IsAuthenticated."""
        settings.RAID_JIRA_WEBHOOK_SECRET = SECRET
        request = _drf_request(APIRequestFactory(), "/whatever")

        result = JiraWebhookSecretAuthentication().authenticate(request)

        assert result is None
