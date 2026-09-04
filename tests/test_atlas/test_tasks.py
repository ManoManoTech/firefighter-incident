"""Tests for Atlas Celery task."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, Mock, patch

import httpx
from django.test import override_settings

from firefighter.atlas.tasks.request_analysis import request_incident_analysis
from firefighter.incidents.models.incident import Incident


def _make_commander(slack_id: str | None = "U123", full_name: str = "Jane Doe") -> Mock:
    """An `IncidentRole` holding command, shaped as `user_slack_handle_or_name` reads it."""
    role = Mock()
    role.user.full_name = full_name
    role.user.slack_user = Mock(slack_id=slack_id) if slack_id else None
    return role


def _make_incident(env_value: str = "PRD", priority_name: str = "P1") -> Mock:
    incident = Mock()
    incident.id = 42
    incident.canonical_name = "20240101-00000042"
    incident.priority.name = priority_name
    incident.environment.value = env_value
    incident.title = "Service outage"
    incident.description = "Something is broken"
    incident.incident_category.name = "checkout"
    incident.created_at.isoformat.return_value = "2024-01-01T00:00:00+00:00"
    # Must be explicit: a bare Mock attribute is not JSON-serialisable.
    incident.commander = _make_commander()
    return incident


def _mock_queryset(incident: Mock) -> Mock:
    qs = MagicMock()
    qs.select_related.return_value = qs
    qs.prefetch_related.return_value = qs
    qs.get.return_value = incident
    return qs


def _sent_payload(mock_instance: Mock) -> dict:
    """Decode the exact bytes POSTed, so assertions cover the signed body."""
    return json.loads(mock_instance.post.call_args.kwargs["content"].decode("utf-8"))


def _ok_response() -> Mock:
    response = Mock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    return response


def _setup_http_client_mock(mock_client_cls: Mock, mock_response: Mock) -> Mock:
    """Wire context-manager protocol on the HttpClient mock and return the instance."""
    mock_instance = mock_client_cls.return_value
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.__exit__.return_value = None
    mock_instance.post.return_value = mock_response
    return mock_instance


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="")
def test_skips_when_secret_missing() -> None:
    with patch("firefighter.incidents.models.incident.Incident.objects") as mock_objects:
        request_incident_analysis.apply(args=[42, "C123"]).get()
        mock_objects.select_related.assert_not_called()


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_posts_payload_to_atlas() -> None:
    incident = _make_incident()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, mock_response)
        request_incident_analysis.apply(args=[42, "C123"]).get()

        mock_instance.post.assert_called_once()
        call_kwargs = mock_instance.post.call_args

        # Verify the signed body is well-formed JSON with the expected fields.
        body_bytes: bytes = call_kwargs.kwargs["content"]
        actual_payload = json.loads(body_bytes.decode("utf-8"))
        assert actual_payload["incident_id"] == "42"
        assert actual_payload["priority"] == "P1"
        assert actual_payload["environment"] == "prd"
        assert actual_payload["slack_channel_id"] == "C123"

        # Verify the HMAC-SHA256 signature over the exact body bytes sent.
        expected_sig = "sha256=" + hmac.new(
            b"secret", body_bytes, hashlib.sha256
        ).hexdigest()
        assert call_kwargs.kwargs["headers"]["X-Atlas-Signature"] == expected_sig
        assert call_kwargs.kwargs["headers"]["Content-Type"] == "application/json"

        # Timeout must be explicit.
        assert call_kwargs.kwargs.get("timeout") == 10.0


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_sends_the_commander_as_a_slack_mention() -> None:
    """Atlas drops the value into a mrkdwn footer, so a mention renders and pings."""
    incident = _make_incident()
    incident.commander = _make_commander(slack_id="U456")

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, _ok_response())
        request_incident_analysis.apply(args=[42, "C123"]).get()

        assert _sent_payload(mock_instance)["commander"] == "<@U456>"


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_falls_back_to_the_commander_full_name_without_a_slack_user() -> None:
    incident = _make_incident()
    incident.commander = _make_commander(slack_id=None, full_name="Jane Doe")

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, _ok_response())
        request_incident_analysis.apply(args=[42, "C123"]).get()

        assert _sent_payload(mock_instance)["commander"] == "Jane Doe"


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_commander_is_null_when_nobody_holds_command() -> None:
    """Atlas supplies its own "unassigned" wording; never send the ∅ sentinel."""
    incident = _make_incident()
    incident.commander = None

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, _ok_response())
        request_incident_analysis.apply(args=[42, "C123"]).get()

        assert _sent_payload(mock_instance)["commander"] is None


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_commander_is_null_when_the_role_has_no_user() -> None:
    incident = _make_incident()
    role = Mock()
    role.user = None
    incident.commander = role

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, _ok_response())
        request_incident_analysis.apply(args=[42, "C123"]).get()

        assert _sent_payload(mock_instance)["commander"] is None


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_aborts_when_incident_missing() -> None:
    """C2: DoesNotExist is caught — task succeeds cleanly with no HTTP call."""
    qs = MagicMock()
    qs.select_related.return_value = qs
    qs.prefetch_related.return_value = qs
    qs.get.side_effect = Incident.DoesNotExist

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", qs),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_instance = _setup_http_client_mock(mock_client_cls, Mock())
        result = request_incident_analysis.apply(args=[42, "C123"])

        assert result.successful()
        mock_instance.post.assert_not_called()


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_does_not_retry_on_4xx() -> None:
    incident = _make_incident()
    http_error = httpx.HTTPStatusError(
        "400 Bad Request",
        request=Mock(),
        response=Mock(status_code=400),
    )
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = http_error

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        _setup_http_client_mock(mock_client_cls, mock_response)
        result = request_incident_analysis.apply(args=[42, "C123"])
        # Task completes without raising (4xx is handled, not re-raised)
        assert result.successful()


@override_settings(ATLAS_URL="https://atlas.example.com/platform-ops/incident/analyze", ATLAS_SHARED_SECRET="secret")  # noqa: S106
def test_retries_on_5xx() -> None:
    incident = _make_incident()
    http_error = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=Mock(),
        response=Mock(status_code=503),
    )
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = http_error

    with (
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_queryset(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        _setup_http_client_mock(mock_client_cls, mock_response)
        result = request_incident_analysis.apply(args=[42, "C123"])
        # Task fails after exhausting retries (5xx is re-raised for retry)
        assert result.failed()
