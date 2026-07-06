from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.jira_app.models import JiraPostMortem
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.tasks.generate_dust_postmortem import generate_dust_postmortem


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


@pytest.mark.django_db
def test_invites_bot_and_posts_message(settings) -> None:
    """Happy path: resolves bot user ID, invites bot then posts the generation request."""
    settings.DUST_SLACK_BOT_NAME = "dust"
    incident = _make_incident_with_channel()
    channel_id = incident.conversation.channel_id

    mock_client = MagicMock()
    mock_client.conversations_invite.return_value = {"ok": True}
    mock_client.chat_postMessage.return_value = {"ok": True}

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        generate_dust_postmortem(incident.id, client=mock_client)

    mock_client.conversations_invite.assert_called_once_with(
        channel=channel_id, users=["UDUSTBOT1"]
    )
    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == channel_id
    assert "UDUSTBOT1" in call_kwargs["text"]
    assert "~IncidentManagementPostMortem" in call_kwargs["text"]


@pytest.mark.django_db
def test_message_includes_jira_postmortem_link(settings) -> None:
    """When a Jira post-mortem exists, its link is embedded in the instruction."""
    settings.DUST_SLACK_BOT_NAME = "dust"
    incident = _make_incident_with_channel()
    jira_pm = JiraPostMortem.objects.create(
        incident=incident,
        jira_issue_key="INCIDENT-27688",
        jira_issue_id="123456",
    )

    mock_client = MagicMock()
    mock_client.conversations_invite.return_value = {"ok": True}
    mock_client.chat_postMessage.return_value = {"ok": True}

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        generate_dust_postmortem(incident.id, client=mock_client)

    text = mock_client.chat_postMessage.call_args.kwargs["text"]
    assert jira_pm.jira_issue_key in text
    assert jira_pm.issue_url in text
    assert "fill in the post-mortem" in text


@pytest.mark.django_db
def test_already_in_channel_is_tolerated(settings) -> None:
    """If bot is already in channel, skip invite silently and still post message."""
    settings.DUST_SLACK_BOT_NAME = "dust"
    incident = _make_incident_with_channel()

    mock_client = MagicMock()
    mock_client.conversations_invite.side_effect = SlackApiError(
        "already_in_channel", {"ok": False, "error": "already_in_channel"}
    )
    mock_client.chat_postMessage.return_value = {"ok": True}

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value="UDUSTBOT1",
    ):
        generate_dust_postmortem(incident.id, client=mock_client)

    mock_client.chat_postMessage.assert_called_once()


@pytest.mark.django_db
def test_skips_when_no_conversation(settings) -> None:
    """If the incident has no Slack channel, do nothing."""
    settings.DUST_SLACK_BOT_NAME = "dust"
    incident = _make_incident_without_channel()

    mock_client = MagicMock()

    generate_dust_postmortem(incident.id, client=mock_client)

    mock_client.conversations_invite.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()


@pytest.mark.django_db
def test_skips_when_bot_not_found(settings) -> None:
    """If the Dust bot is not found in the workspace, do nothing."""
    settings.DUST_SLACK_BOT_NAME = "dust"
    incident = _make_incident_with_channel()

    mock_client = MagicMock()

    with patch(
        "firefighter.slack.tasks.generate_dust_postmortem._resolve_bot_user_id",
        return_value=None,
    ):
        generate_dust_postmortem(incident.id, client=mock_client)

    mock_client.conversations_invite.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()
