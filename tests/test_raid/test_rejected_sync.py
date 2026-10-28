"""REJECTED incidents and incident origin, synced with Jira in both directions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest
from django.core.cache import cache

from firefighter.incidents.enums import ClosureReason, IncidentOrigin, IncidentStatus
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.partner import Partner
from firefighter.raid.serializers import JiraWebhookUpdateSerializer
from firefighter.raid.signals.incident_updated import (
    incident_origin_updated_sync_jira_labels,
    incident_updated_close_ticket_when_mitigated_or_postmortem,
)

CLIENT = "firefighter.raid.signals.incident_updated.client"


@pytest.fixture(autouse=True)
def clear_sync_cache() -> None:
    cache.clear()


@pytest.fixture
def rejected_incident(incident_factory: Any, jira_ticket_factory: Any) -> Any:
    incident = incident_factory(
        _status=IncidentStatus.REJECTED,
        closure_reason=ClosureReason.DUPLICATE,
        closure_reference="#15637",
    )
    incident.jira_ticket = jira_ticket_factory(incident=incident)
    return incident


def _reject(incident: Any) -> None:
    incident_updated_close_ticket_when_mitigated_or_postmortem(
        sender="update_status",
        incident=incident,
        incident_update=IncidentUpdate(
            incident=incident, _status=IncidentStatus.REJECTED, message="Same as #15637"
        ),
        updated_fields=["_status"],
    )


@pytest.mark.django_db
class TestRejectTicket:
    @patch(f"{CLIENT}.transition_issue_auto")
    @patch(f"{CLIENT}.transition_issue_by_name")
    @patch(f"{CLIENT}.get_issue_status_name", return_value="In Progress")
    def test_applies_reject_with_its_reason_then_closes(
        self, status: Mock, by_name: Mock, auto: Mock, rejected_incident: Any
    ) -> None:
        _reject(rejected_incident)

        status.assert_called_once()

        by_name.assert_called_once()
        args, kwargs = by_name.call_args
        assert args == (rejected_incident.jira_ticket.id, "Reject")
        assert kwargs["fields"] == {"customfield_10943": {"value": "Duplicated"}}
        # The exact reason goes in the comment: the Jira field only has coarse options
        assert "Duplicate incident" in kwargs["comment"]
        assert "#15637" in kwargs["comment"]
        assert "Same as #15637" in kwargs["comment"]
        auto.assert_called_once_with(rejected_incident.jira_ticket.id, "Closed", ANY)

    @patch(f"{CLIENT}.transition_issue_auto")
    @patch(f"{CLIENT}.transition_issue_by_name")
    @patch(f"{CLIENT}.add_comment")
    @patch(f"{CLIENT}.get_issue_status_name", return_value="Reporter validation")
    def test_from_reporter_validation_only_comments_and_closes(
        self,
        status: Mock,
        comment: Mock,
        by_name: Mock,
        auto: Mock,
        rejected_incident: Any,
    ) -> None:
        _reject(rejected_incident)

        status.assert_called_once()

        by_name.assert_not_called()
        comment.assert_called_once()
        auto.assert_called_once()

    @patch(f"{CLIENT}.transition_issue_auto")
    @patch(f"{CLIENT}.transition_issue_by_name")
    @patch(f"{CLIENT}.add_comment")
    @patch(f"{CLIENT}.get_issue_status_name", return_value="Closed")
    def test_an_already_closed_ticket_only_gets_the_comment(
        self,
        status: Mock,
        comment: Mock,
        by_name: Mock,
        auto: Mock,
        rejected_incident: Any,
    ) -> None:
        _reject(rejected_incident)

        status.assert_called_once()

        comment.assert_called_once()
        by_name.assert_not_called()
        auto.assert_not_called()

    @patch(f"{CLIENT}.transition_issue_auto")
    @patch(
        f"{CLIENT}.transition_issue_by_name", side_effect=ValueError("not available")
    )
    @patch(f"{CLIENT}.get_issue_status_name", return_value="Incoming")
    def test_a_failed_rejection_does_not_close_the_ticket(
        self, status: Mock, by_name: Mock, auto: Mock, rejected_incident: Any
    ) -> None:
        _reject(rejected_incident)

        status.assert_called_once()
        by_name.assert_called_once()

        auto.assert_not_called()


@pytest.mark.django_db
class TestOriginLabels:
    @patch(f"{CLIENT}.update_issue_fields")
    @patch(f"{CLIENT}.get_issue_labels")
    def test_a_partner_origin_adds_its_labels(
        self,
        get_labels: Mock,
        update: Mock,
        incident_factory: Any,
        jira_ticket_factory: Any,
    ) -> None:
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = incident_factory(origin=IncidentOrigin.PARTNER, partner=algolia)
        incident.jira_ticket = jira_ticket_factory(incident=incident)
        get_labels.return_value = ["goldenList", "partner:stripe"]

        incident_origin_updated_sync_jira_labels(sender=None, incident=incident)

        update.assert_called_once_with(
            incident.jira_ticket.id,
            labels=["goldenList", "partner-caused", "partner:algolia"],
        )

    @patch(f"{CLIENT}.update_issue_fields")
    @patch(f"{CLIENT}.get_issue_labels")
    def test_an_internal_origin_removes_them(
        self,
        get_labels: Mock,
        update: Mock,
        incident_factory: Any,
        jira_ticket_factory: Any,
    ) -> None:
        incident = incident_factory(origin=IncidentOrigin.INTERNAL)
        incident.jira_ticket = jira_ticket_factory(incident=incident)
        get_labels.return_value = ["partner-caused", "partner:algolia", "keep"]

        incident_origin_updated_sync_jira_labels(sender=None, incident=incident)

        update.assert_called_once_with(incident.jira_ticket.id, labels=["keep"])


def _webhook(
    incident: Any, *, to_status: str, resolution: str | None, reason: str | None
) -> None:
    fields: dict[str, Any] = {
        "resolution": {"name": resolution} if resolution else None,
        "customfield_10943": {"value": reason} if reason else None,
    }
    payload = {
        "issue": {"id": "123", "key": "INCIDENT-1", "fields": fields},
        "changelog": {
            "items": [
                {"field": "status", "fromString": "in progress", "toString": to_status}
            ]
        },
        "user": {"displayName": "A human", "accountId": "human-account"},
        "webhookEvent": "jira:issue_updated",
    }
    fake_queryset = SimpleNamespace(get=lambda **_: SimpleNamespace(incident=incident))
    with (
        patch(
            "firefighter.raid.serializers.JiraTicket.objects.select_related",
            return_value=fake_queryset,
        ),
        patch(
            "firefighter.raid.serializers.alert_slack_update_ticket", return_value=True
        ),
    ):
        serializer = JiraWebhookUpdateSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        serializer.save()


@pytest.mark.django_db
class TestRejectedInJira:
    @staticmethod
    def test_rejecting_the_ticket_rejects_the_incident(incident_factory: Any) -> None:
        incident = incident_factory(_status=IncidentStatus.MITIGATING)

        _webhook(
            incident,
            to_status="Reporter validation",
            resolution="Rejected",
            reason="Duplicated",
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.REJECTED
        assert incident.closure_reason == ClosureReason.DUPLICATE

    @staticmethod
    def test_any_other_reject_reason_is_a_false_alarm(incident_factory: Any) -> None:
        incident = incident_factory(_status=IncidentStatus.INVESTIGATING)

        _webhook(
            incident,
            to_status="Reporter validation",
            resolution="Rejected",
            reason="Could not reproduce",
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.REJECTED
        assert incident.closure_reason == ClosureReason.FALSE_POSITIVE

    @staticmethod
    def test_closing_a_rejected_ticket_keeps_the_incident_rejected(
        incident_factory: Any,
    ) -> None:
        incident = incident_factory(
            _status=IncidentStatus.REJECTED, closure_reason=ClosureReason.DUPLICATE
        )

        _webhook(
            incident, to_status="Closed", resolution="Rejected", reason="Duplicated"
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.REJECTED

    @staticmethod
    def test_a_resolved_ticket_still_mitigates_the_incident(
        incident_factory: Any,
    ) -> None:
        incident = incident_factory(_status=IncidentStatus.MITIGATING)

        _webhook(
            incident, to_status="Reporter validation", resolution="Done", reason=None
        )

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED
