"""Tests for Atlas Celery task."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import httpx
from django.test import override_settings

from firefighter.atlas.tasks.request_analysis import request_incident_analysis


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
    return incident


def _mock_select_related(incident: Mock) -> Mock:
    qs = MagicMock()
    qs.select_related.return_value = qs
    qs.get.return_value = incident
    return qs


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
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_select_related(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.post.return_value = mock_response
        request_incident_analysis.apply(args=[42, "C123"]).get()

        mock_client_cls.return_value.post.assert_called_once()
        call_kwargs = mock_client_cls.return_value.post.call_args
        assert call_kwargs.kwargs["headers"] == {"X-Atlas-Secret": "secret"}
        payload = call_kwargs.kwargs["json"]
        assert payload["incident_id"] == "42"
        assert payload["priority"] == "P1"
        assert payload["environment"] == "prd"
        assert payload["slack_channel_id"] == "C123"


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
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_select_related(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.post.return_value = mock_response
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
        patch("firefighter.incidents.models.incident.Incident.objects", _mock_select_related(incident)),
        patch("firefighter.firefighter.http_client.HttpClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.post.return_value = mock_response
        result = request_incident_analysis.apply(args=[42, "C123"])
        # Task fails after exhausting retries (5xx is re-raised for retry)
        assert result.failed()
