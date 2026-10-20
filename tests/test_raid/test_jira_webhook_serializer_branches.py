"""Tests for the JiraWebhookUpdateSerializer branches and the Landbot attachment guards.

Same harness as test_jira_priority_sync: the JiraTicket lookup is patched to return a
ticket linked to the given incident, and the Slack alert is patched.
"""

from __future__ import annotations

import logging
import socket
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from django.core.cache import cache
from rest_framework import serializers

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.client import SlackNotificationError
from firefighter.raid.models import JiraTicket
from firefighter.raid.serializers import (
    ATTACHMENT_MAX_COUNT,
    ATTACHMENT_URL_MAX_LENGTH,
    JiraWebhookUpdateSerializer,
    LandbotIssueRequestSerializer,
)
from firefighter.raid.utils import normalize_cache_value
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.models.incident_channel import IncidentChannel

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

FF_ACCOUNT_ID = "ff-service-account"


@pytest.fixture(autouse=True)
def clear_sync_cache() -> None:
    cache.clear()


@pytest.fixture(autouse=True)
def alert(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "firefighter.raid.serializers.alert_slack_update_ticket", return_value=True
    )


@pytest.fixture
def incident(mocker: MockerFixture) -> Incident:
    incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)
    mocker.patch.object(incident, "create_incident_update")
    return incident


def _payload(change_items: list[dict[str, Any]], **issue: Any) -> dict[str, Any]:
    return {
        "issue": issue or {"id": "123", "key": "IMPACT-1"},
        "changelog": {"items": change_items},
        "user": {"displayName": "jira-user", "accountId": "human-1"},
        "webhookEvent": "jira:issue_updated",
    }


def _run(payload: dict[str, Any], ticket: object | None) -> bool:
    fake_qs = SimpleNamespace(get=lambda **_kwargs: ticket)
    with patch(
        "firefighter.raid.serializers.JiraTicket.objects.select_related",
        return_value=fake_qs,
    ):
        serializer = JiraWebhookUpdateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        return serializer.save()


def _status_change(to: str, frm: str = "Incoming") -> dict[str, str]:
    return {"field": "status", "fromString": frm, "toString": to}


def _priority_change(to: str | None) -> dict[str, str | None]:
    return {"field": "Priority", "fieldId": "customfield_11064", "toString": to}


@pytest.mark.django_db
class TestCreate:
    @staticmethod
    def test_no_changelog_items_is_a_no_op(alert: MagicMock) -> None:
        assert _run(_payload([]), ticket=None) is True
        alert.assert_not_called()

    @staticmethod
    def test_ticket_without_incident_still_alerts_slack(alert: MagicMock) -> None:
        payload = _payload([_status_change("in progress"), {"field": "labels"}])

        assert _run(payload, ticket=SimpleNamespace(incident=None)) is True
        alert.assert_called_once()

    @staticmethod
    def test_missing_issue_id_fails_the_slack_alert(alert: MagicMock) -> None:
        payload = _payload([_status_change("in progress")], key="IMPACT-1")

        with pytest.raises(SlackNotificationError):
            _run(payload, ticket=SimpleNamespace(incident=None))
        alert.assert_not_called()

    @staticmethod
    def test_slack_alert_failure_raises(alert: MagicMock) -> None:
        alert.return_value = False

        with pytest.raises(SlackNotificationError):
            _run(
                _payload([_status_change("in progress")]),
                ticket=SimpleNamespace(incident=None),
            )


@pytest.mark.django_db
class TestSyncToIncident:
    @staticmethod
    def test_changes_authored_by_firefighter_are_ignored(
        alert: MagicMock, incident: Incident, settings: Any
    ) -> None:
        settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID = FF_ACCOUNT_ID
        payload = _payload([_status_change("in progress")])
        payload["user"]["accountId"] = FF_ACCOUNT_ID

        _run(payload, ticket=SimpleNamespace(incident=incident))

        alert.assert_not_called()
        incident.create_incident_update.assert_not_called()

    @staticmethod
    def test_without_configured_ff_account_every_change_syncs(
        alert: MagicMock, incident: Incident, settings: Any
    ) -> None:
        settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID = ""

        _run(
            _payload([_status_change("in progress")]),
            ticket=SimpleNamespace(incident=incident),
        )

        alert.assert_called_once()
        incident.create_incident_update.assert_called_once()

    @staticmethod
    def test_change_just_sent_by_impact_is_not_reflected_back(
        alert: MagicMock, incident: Incident
    ) -> None:
        cache_key = f"sync:impact_to_jira:{incident.id}:status:{normalize_cache_value('in progress')}"
        cache.set(cache_key, value=True)

        _run(
            _payload([_status_change("in progress")]),
            ticket=SimpleNamespace(incident=incident),
        )

        alert.assert_not_called()
        incident.create_incident_update.assert_not_called()
        # The marker is consumed, so a later identical human change does sync
        assert cache.get(cache_key) is None

    @staticmethod
    @pytest.mark.parametrize(
        "change", [_status_change("in progress"), _priority_change("2")]
    )
    def test_slack_alert_failure_raises(
        alert: MagicMock, incident: Incident, change: dict[str, Any]
    ) -> None:
        alert.return_value = False

        with pytest.raises(SlackNotificationError):
            _run(_payload([change]), ticket=SimpleNamespace(incident=incident))
        incident.create_incident_update.assert_not_called()


@pytest.mark.django_db
class TestStatusUpdate:
    @staticmethod
    def test_unmapped_jira_status_is_ignored(
        alert: MagicMock, incident: Incident
    ) -> None:
        _run(
            _payload([_status_change("Code Review")]),
            ticket=SimpleNamespace(incident=incident),
        )

        alert.assert_called_once()
        incident.create_incident_update.assert_not_called()

    @staticmethod
    def test_close_from_unknown_jira_status_is_ignored(incident: Incident) -> None:
        change = _status_change("Closed", frm="Code Review")

        _run(_payload([change]), ticket=SimpleNamespace(incident=incident))

        incident.create_incident_update.assert_not_called()

    @staticmethod
    def test_incident_already_at_the_status_is_a_no_op(incident: Incident) -> None:
        incident._status = IncidentStatus.MITIGATING

        _run(
            _payload([_status_change("in progress")]),
            ticket=SimpleNamespace(incident=incident),
        )

        incident.create_incident_update.assert_not_called()

    @staticmethod
    def test_blocked_close_notifies_the_channel(
        incident: Incident, mocker: MockerFixture
    ) -> None:
        IncidentChannelFactory.create(incident=incident)
        mocker.patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("MISSING_KEY_EVENTS", "Key events are missing")]),
        )
        send = mocker.patch.object(IncidentChannel, "send_message_and_save")

        _run(
            _payload([_status_change("Closed", frm="Reporter validation")]),
            ticket=SimpleNamespace(incident=incident),
        )

        incident.create_incident_update.assert_not_called()
        send.assert_called_once()

    @staticmethod
    def test_blocked_close_survives_a_channel_failure(
        incident: Incident, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        IncidentChannelFactory.create(incident=incident)
        mocker.patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("MISSING_KEY_EVENTS", "Key events are missing")]),
        )
        mocker.patch.object(
            IncidentChannel,
            "send_message_and_save",
            side_effect=RuntimeError("slack down"),
        )

        assert (
            _run(
                _payload([_status_change("Closed", frm="Reporter validation")]),
                ticket=SimpleNamespace(incident=incident),
            )
            is True
        )
        incident.create_incident_update.assert_not_called()
        assert "Failed to notify incident channel" in caplog.text


@pytest.mark.django_db
class TestPriorityUpdate:
    @staticmethod
    def test_unmapped_priority_is_ignored(incident: Incident) -> None:
        _run(
            _payload([_priority_change("Urgent-ish")]),
            ticket=SimpleNamespace(incident=incident),
        )

        incident.create_incident_update.assert_not_called()

    @staticmethod
    def test_incident_already_at_the_priority_is_a_no_op(
        incident: Incident, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Pin the priority: the factory draws it from a session-wide cyclic iterator,
        # so an unpinned incident may not have a priority Jira can map to
        incident.priority = Priority.objects.get(value=3)

        with caplog.at_level(logging.DEBUG, logger="firefighter.raid.serializers"):
            _run(
                _payload([_priority_change("3")]),
                ticket=SimpleNamespace(incident=incident),
            )

        incident.create_incident_update.assert_not_called()
        assert f"Incident {incident.id} already at priority 3" in caplog.text

    @staticmethod
    def test_missing_impact_priority_is_ignored(
        incident: Incident, mocker: MockerFixture
    ) -> None:
        target = 5 if incident.priority.value != 5 else 4
        mocker.patch(
            "firefighter.raid.serializers.Priority.objects.get",
            side_effect=Priority.DoesNotExist,
        )

        _run(
            _payload([_priority_change(str(target))]),
            ticket=SimpleNamespace(incident=incident),
        )

        incident.create_incident_update.assert_not_called()


@pytest.mark.django_db
class TestSkipDueToRecentImpactChange:
    """The helper is also guarded on its own, independently of the caller's lookups."""

    @staticmethod
    def test_without_ticket_key() -> None:
        assert not JiraWebhookUpdateSerializer._skip_due_to_recent_impact_change(
            None, "status", _status_change("in progress")
        )

    @staticmethod
    def test_unknown_ticket() -> None:
        assert not JiraWebhookUpdateSerializer._skip_due_to_recent_impact_change(
            "UNKNOWN-1", "status", _status_change("in progress")
        )

    @staticmethod
    def test_ticket_without_incident(mocker: MockerFixture) -> None:
        fake_qs = SimpleNamespace(get=lambda **_kwargs: SimpleNamespace(incident=None))
        mocker.patch.object(JiraTicket.objects, "select_related", return_value=fake_qs)

        assert not JiraWebhookUpdateSerializer._skip_due_to_recent_impact_change(
            "IMPACT-1", "status", _status_change("in progress")
        )


def test_parse_priority_value_of_nothing() -> None:
    assert JiraWebhookUpdateSerializer._parse_priority_value(None) is None


class TestAttachmentGuards:
    @staticmethod
    def test_too_many_attachments_are_rejected() -> None:
        urls = ",".join(
            f"https://files.example/{i}" for i in range(ATTACHMENT_MAX_COUNT + 1)
        )

        with pytest.raises(serializers.ValidationError, match="Too many attachments"):
            LandbotIssueRequestSerializer().validate_attachments(urls)

    @staticmethod
    def test_overlong_url_is_rejected() -> None:
        url = "https://files.example/" + "a" * ATTACHMENT_URL_MAX_LENGTH

        with pytest.raises(serializers.ValidationError, match="exceeds"):
            LandbotIssueRequestSerializer().validate_attachments(url)

    @staticmethod
    def test_unresolvable_host_is_rejected(mocker: MockerFixture) -> None:
        mocker.patch(
            "firefighter.raid.serializers.socket.getaddrinfo",
            side_effect=socket.gaierror("no such host"),
        )

        with pytest.raises(serializers.ValidationError, match="could not be resolved"):
            LandbotIssueRequestSerializer().validate_attachments(
                "https://nowhere.invalid/a"
            )
