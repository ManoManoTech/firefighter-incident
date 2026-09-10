from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.models import JiraPostMortem
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.tasks.generate_dust_postmortem import generate_dust_postmortem

WEBHOOK_URL = "https://dust.example.com/webhooks/postmortem"
WEBHOOK_SECRET = "s3cr3t"  # noqa: S105 - test fixture, not a real secret


def _configure(settings) -> None:
    settings.DUST_SLACK_BOT_NAME = "dust"
    settings.DUST_WEBHOOK_URL = WEBHOOK_URL
    settings.DUST_WEBHOOK_SECRET = WEBHOOK_SECRET


def _make_incident_with_channel() -> object:
    user = UserFactory.build()
    user.save()
    incident = IncidentFactory.build(created_by=user)
    incident.save()
    channel = IncidentChannelFactory.build(incident=incident)
    channel.save()
    incident.refresh_from_db()
    return incident


def _make_incident_without_channel() -> object:
    user = UserFactory.build()
    user.save()
    incident = IncidentFactory.build(created_by=user)
    incident.save()
    return incident


def _with_postmortem(incident: object, key: str = "INCIDENT-27688") -> JiraPostMortem:
    return JiraPostMortem.objects.create(
        incident=incident, jira_issue_key=key, jira_issue_id="123456"
    )


def _run(incident_id: int, slack_client: MagicMock) -> MagicMock:
    """Run the task with the HTTP client mocked; returns the mocked client."""
    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem.HttpClient"
    ) as http_class:
        http_client = http_class.return_value.__enter__.return_value
        http_client.post.return_value = MagicMock(status_code=200)
        generate_dust_postmortem(incident_id, client=slack_client)
    return http_client


def _slack_client() -> MagicMock:
    client = MagicMock()
    client.conversations_invite.return_value = {"ok": True}
    return client


@pytest.mark.django_db
def test_calls_the_webhook_with_the_channel_and_the_ticket(settings) -> None:
    _configure(settings)
    incident = _make_incident_with_channel()
    jira_pm = _with_postmortem(incident)
    slack_client = _slack_client()

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        http_client = _run(incident.id, slack_client)

    slack_client.conversations_invite.assert_called_once_with(
        channel=incident.conversation.channel_id, users=["UDUSTBOT1"]
    )
    url, kwargs = http_client.post.call_args.args[0], http_client.post.call_args.kwargs
    assert url == WEBHOOK_URL
    payload = json.loads(kwargs["content"])
    # Dust imposes no schema: the agent addresses the fields we choose to send,
    # so the two values it needs are fields of their own, not prose to parse.
    assert payload["jira_issue_key"] == jira_pm.jira_issue_key
    assert payload["channel"]["id"] == incident.conversation.channel_id
    assert payload["channel"]["name"] == incident.conversation.name
    assert payload["incident"]["id"] == incident.id
    message = payload["message"]
    assert jira_pm.jira_issue_key in message
    assert incident.conversation.channel_id in message
    # The instruction is no longer posted in Slack: the webhook is the trigger.
    slack_client.chat_postMessage.assert_not_called()


@pytest.mark.django_db
def test_signature_covers_the_exact_bytes_that_are_sent(settings) -> None:
    """Signing a dict and letting the client re-serialize it would break the signature."""
    _configure(settings)
    incident = _make_incident_with_channel()
    _with_postmortem(incident)

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        http_client = _run(incident.id, _slack_client())

    kwargs = http_client.post.call_args.kwargs
    body = kwargs["content"]
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    assert kwargs["headers"]["signature"] == f"sha256={expected}"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert isinstance(body, bytes)


@pytest.mark.django_db
def test_already_in_channel_is_tolerated(settings) -> None:
    _configure(settings)
    incident = _make_incident_with_channel()
    _with_postmortem(incident)
    slack_client = _slack_client()
    slack_client.conversations_invite.side_effect = SlackApiError(
        "already_in_channel", {"ok": False, "error": "already_in_channel"}
    )

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        http_client = _run(incident.id, slack_client)

    http_client.post.assert_called_once()


@pytest.mark.django_db
def test_missing_bot_does_not_stop_the_trigger(settings) -> None:
    """The bot is only needed for the agent's reply; the webhook is what triggers it."""
    _configure(settings)
    incident = _make_incident_with_channel()
    _with_postmortem(incident)
    slack_client = _slack_client()

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value=None,
    ):
        http_client = _run(incident.id, slack_client)

    slack_client.conversations_invite.assert_not_called()
    http_client.post.assert_called_once()


@pytest.mark.django_db
def test_skips_when_no_conversation(settings) -> None:
    _configure(settings)
    incident = _make_incident_without_channel()
    slack_client = _slack_client()

    http_client = _run(incident.id, slack_client)

    slack_client.conversations_invite.assert_not_called()
    http_client.post.assert_not_called()


@pytest.mark.django_db
def test_skips_when_the_incident_has_no_jira_postmortem(settings) -> None:
    """There would be no ticket for the agent to fill in."""
    _configure(settings)
    incident = _make_incident_with_channel()

    http_client = _run(incident.id, _slack_client())

    http_client.post.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("missing", ["DUST_WEBHOOK_URL", "DUST_WEBHOOK_SECRET"])
def test_skips_when_the_webhook_is_not_configured(settings, missing: str) -> None:
    """An unsigned or targetless call would be rejected anyway."""
    _configure(settings)
    setattr(settings, missing, None)
    incident = _make_incident_with_channel()
    _with_postmortem(incident)

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        http_client = _run(incident.id, _slack_client())

    http_client.post.assert_not_called()


@pytest.mark.django_db
def test_http_error_is_raised_so_celery_retries(settings) -> None:
    _configure(settings)
    incident = _make_incident_with_channel()
    _with_postmortem(incident)

    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=MagicMock()
    )
    with (
        patch(
            "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
            return_value="UDUSTBOT1",
        ),
        patch(
            "firefighter.slack.tasks.generate_dust_postmortem.HttpClient"
        ) as http_class,
    ):
        http_class.return_value.__enter__.return_value.post.return_value = response
        with pytest.raises(httpx.HTTPStatusError):
            generate_dust_postmortem(incident.id, client=_slack_client())
