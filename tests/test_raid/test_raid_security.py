"""Security regression tests for the raid endpoints.

Covers the two vulnerabilities that motivated this module:
    - `POST /api/v2/firefighter/raid/jira_bot` must require authentication.
    - The `attachments` field must reject URLs pointing at private/link-local
      networks so the server cannot be coerced into fetching cloud metadata
      or internal services on behalf of the caller.
"""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from firefighter.incidents.factories import UserFactory
from firefighter.raid.serializers import parse_attachment_urls

JIRA_BOT_URL = "/api/v2/firefighter/raid/jira_bot"

BASE_PAYLOAD: dict[str, object] = {
    "summary": "sec-test",
    "description": "sec-test",
    "seller_contract_id": "",
    "zoho": "",
    "platform": "FR",
    "reporter_email": "sec-test@manomano.com",
    "incident_category": "",
    "suggested_team_routing": "x",
    "priority": 4,
    "business_impact": "Low",
    "issue_type": "Incident",
}


@pytest.mark.django_db
class TestJiraBotAuthentication:
    def test_anonymous_post_is_rejected(self) -> None:
        client = APIClient()
        response = client.post(JIRA_BOT_URL, data=BASE_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestJiraBotAttachmentsSSRF:
    @pytest.mark.parametrize(
        "attachments",
        [
            "http://127.0.0.1/leak.png",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            "http://10.0.0.1/leak.png",
            "http://192.168.1.1/leak.png",
            "http://[::1]/leak.png",
            "['http://169.254.169.254/leak']",
        ],
    )
    def test_private_or_link_local_hosts_are_rejected(
        self, attachments: str
    ) -> None:
        client = APIClient()
        client.force_authenticate(user=UserFactory.create())
        payload = {**BASE_PAYLOAD, "attachments": attachments}
        response = client.post(JIRA_BOT_URL, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert any(
            err.get("attr") == "attachments" for err in body.get("errors", [])
        ), body

    @pytest.mark.parametrize(
        "attachments",
        [
            "file:///etc/passwd",
            "gopher://attacker.example/exploit",
        ],
    )
    def test_non_http_schemes_are_rejected(self, attachments: str) -> None:
        client = APIClient()
        client.force_authenticate(user=UserFactory.create())
        payload = {**BASE_PAYLOAD, "attachments": attachments}
        response = client.post(JIRA_BOT_URL, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert any(
            err.get("attr") == "attachments" for err in body.get("errors", [])
        ), body


class TestParseAttachmentUrls:
    """Parser must tolerate absent, empty and Landbot's legacy list-as-string payloads."""

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_empty_returns_empty_list(self, raw: str | None) -> None:
        assert parse_attachment_urls(raw) == []

    def test_single_url(self) -> None:
        assert parse_attachment_urls("https://example.com/a.png") == [
            "https://example.com/a.png"
        ]

    def test_legacy_stringified_list_from_landbot(self) -> None:
        raw = "['https://example.com/a.png', 'https://example.com/b.png']"
        assert parse_attachment_urls(raw) == [
            "https://example.com/a.png",
            "https://example.com/b.png",
        ]
