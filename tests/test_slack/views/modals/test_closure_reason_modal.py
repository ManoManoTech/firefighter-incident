"""Tests for ClosureReasonModal - Slack modal for closing incidents with a reason."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
from firefighter.slack.slack_incident_context import (
    _extract_incident_id_from_private_metadata,
)
from firefighter.slack.views.modals.closure_reason import ClosureReasonModal


@pytest.mark.django_db
class TestClosureReasonModalMessageTabDisabled:
    """Test ClosureReasonModal handles messages_tab_disabled gracefully."""

    def test_closure_reason_handles_messages_tab_disabled(
        self, caplog: pytest.LogCaptureFixture, mocker
    ) -> None:
        """Test that messages_tab_disabled error is handled gracefully with warning log."""
        # Create test data
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(
            _status=IncidentStatus.INVESTIGATING, created_by=user
        )
        incident.save()

        # Mock can_be_closed to return True so the closure can proceed
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=mocker.PropertyMock,
            return_value=(True, []),
        )

        # Create modal and mock
        modal = ClosureReasonModal()
        ack = MagicMock()

        # Create valid form submission
        body = {
            "view": {
                "state": {
                    "values": {
                        "closure_reason": {
                            "select_closure_reason": {
                                "selected_option": {"value": ClosureReason.CANCELLED}
                            }
                        },
                        "closure_reference": {"input_closure_reference": {"value": ""}},
                        "closure_message": {
                            "input_closure_message": {"value": "Test closure message"}
                        },
                    }
                },
                "private_metadata": str(incident.id),
            },
            "user": {"id": "U123456"},
        }

        # Mock respond to raise messages_tab_disabled error
        slack_error_response = MagicMock()
        slack_error_response.get.return_value = "messages_tab_disabled"

        with patch(
            "firefighter.slack.views.modals.closure_reason.respond"
        ) as mock_respond:
            mock_respond.side_effect = SlackApiError(
                message="The request to the Slack API failed.",
                response=slack_error_response,
            )

            # Execute
            result = modal.handle_modal_fn(
                ack=ack, body=body, incident=incident, user=user
            )

            # Assertions
            assert result is True  # Incident should still be closed successfully

            # Verify incident was closed
            incident.refresh_from_db()
            assert incident.status == IncidentStatus.CLOSED
            assert incident.closure_reason == ClosureReason.CANCELLED

            # Verify warning was logged
            assert any(
                "Cannot send DM to user" in record.message
                and record.levelname == "WARNING"
                for record in caplog.records
            )

    def test_closure_reason_reraises_other_slack_errors(self, mocker) -> None:
        """Test that other Slack API errors are re-raised."""
        # Create test data
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(
            _status=IncidentStatus.INVESTIGATING, created_by=user
        )
        incident.save()

        # Mock can_be_closed to return True so the closure can proceed
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=mocker.PropertyMock,
            return_value=(True, []),
        )

        # Create modal and mock
        modal = ClosureReasonModal()
        ack = MagicMock()

        # Create valid form submission
        body = {
            "view": {
                "state": {
                    "values": {
                        "closure_reason": {
                            "select_closure_reason": {
                                "selected_option": {"value": ClosureReason.CANCELLED}
                            }
                        },
                        "closure_reference": {"input_closure_reference": {"value": ""}},
                        "closure_message": {
                            "input_closure_message": {"value": "Test closure message"}
                        },
                    }
                },
                "private_metadata": str(incident.id),
            },
            "user": {"id": "U123456"},
        }

        # Mock respond to raise different Slack error
        slack_error_response = MagicMock()
        slack_error_response.get.return_value = "channel_not_found"

        with patch(
            "firefighter.slack.views.modals.closure_reason.respond"
        ) as mock_respond:
            mock_respond.side_effect = SlackApiError(
                message="The request to the Slack API failed.",
                response=slack_error_response,
            )

            # Execute and expect exception
            with pytest.raises(SlackApiError):
                modal.handle_modal_fn(ack=ack, body=body, incident=incident, user=user)


@pytest.mark.django_db
class TestClosureReasonModalEarlyClosureBypass:
    """Test early-closure path respects submitted closure reason."""

    def test_allows_early_closure_with_submitted_reason(self, settings) -> None:
        """Ensure can_be_closed passes when a closure reason is provided for early closure."""
        settings.ENABLE_JIRA_POSTMORTEM = True

        # Ensure required priority/environment for needs_postmortem + PRD
        priority = Priority.objects.create(
            name="P1-test",
            value=9991,
            description="P1 test",
            order=9991,
            needs_postmortem=True,
        )
        env, _ = Environment.objects.get_or_create(
            value="PRD",
            defaults={
                "name": "Production",
                "description": "Production",
                "order": 9991,
            },
        )

        user = UserFactory.create()
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            created_by=user,
            priority=priority,
            environment=env,
        )

        modal = ClosureReasonModal()
        ack = MagicMock()

        body = {
            "view": {
                "state": {
                    "values": {
                        "closure_reason": {
                            "select_closure_reason": {
                                "selected_option": {"value": ClosureReason.CANCELLED}
                            }
                        },
                        "closure_reference": {
                            "input_closure_reference": {"value": "INC-42"}
                        },
                        "closure_message": {
                            "input_closure_message": {
                                "value": "Closing early with reason"
                            }
                        },
                    }
                },
                "private_metadata": str(incident.id),
            },
            "user": {"id": "U123456"},
        }

        with patch(
            "firefighter.slack.views.modals.closure_reason.respond"
        ) as mock_respond:
            mock_respond.return_value = None

            result = modal.handle_modal_fn(
                ack=ack,
                body=body,
                incident=incident,
                user=user,
            )

        # Early closure should succeed and close the incident
        assert result is True
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CLOSED
        assert incident.closure_reason == ClosureReason.CANCELLED
        assert incident.closure_reference == "INC-42"

        # Ack should clear modal stack
        ack.assert_called_once_with(response_action="clear")


@pytest.mark.django_db
class TestClosureReasonModalCarryOver:
    """Closure reason modal must apply fields carried over from Update Status."""

    def test_build_modal_fn_keeps_plain_metadata_without_carry_over(self) -> None:
        """No carry-over → keep the legacy plain-int private_metadata format."""
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)
        modal = ClosureReasonModal()

        view = modal.build_modal_fn(body={}, incident=incident)

        assert view.private_metadata == str(incident.id)

    def test_build_modal_fn_encodes_carry_over_into_private_metadata(self) -> None:
        """Carry-over fields should be serialised into the JSON private_metadata."""
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)
        modal = ClosureReasonModal()

        carry_over = {
            "priority_id": "00000000-0000-0000-0000-000000000010",
            "incident_category_id": "00000000-0000-0000-0000-000000000020",
        }
        view = modal.build_modal_fn(body={}, incident=incident, carry_over=carry_over)

        parsed = json.loads(view.private_metadata)
        assert parsed == {"incident_id": incident.id, "carry_over": carry_over}

        # The incident resolver must still recover the incident from this JSON format
        assert _extract_incident_id_from_private_metadata(view.private_metadata) == incident.id

    def test_build_modal_fn_drops_unknown_carry_over_keys(self) -> None:
        """Only whitelisted carry-over keys are serialised."""
        incident = IncidentFactory.create(_status=IncidentStatus.INVESTIGATING)
        modal = ClosureReasonModal()

        view = modal.build_modal_fn(
            body={},
            incident=incident,
            carry_over={
                "priority_id": "00000000-0000-0000-0000-000000000010",
                "rogue_field": "should-be-dropped",
            },
        )

        parsed = json.loads(view.private_metadata)
        assert parsed["carry_over"] == {
            "priority_id": "00000000-0000-0000-0000-000000000010",
        }

    def test_handle_modal_fn_applies_carried_over_priority(self, mocker) -> None:
        """Submitting the closure modal must re-apply the priority carried over."""
        priority_initial = Priority.objects.create(
            name="P1-test-init",
            value=9001,
            description="P1 test init",
            order=9001,
            needs_postmortem=True,
        )
        priority_new = Priority.objects.create(
            name="P3-test-carry",
            value=9003,
            description="P3 carry-over",
            order=9003,
            needs_postmortem=False,
        )

        user = UserFactory.create()
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            created_by=user,
            priority=priority_initial,
        )

        # Allow early closure regardless of validation details
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=mocker.PropertyMock,
            return_value=(True, []),
        )

        modal = ClosureReasonModal()
        ack = MagicMock()

        body = {
            "view": {
                "state": {
                    "values": {
                        "closure_reason": {
                            "select_closure_reason": {
                                "selected_option": {"value": ClosureReason.CANCELLED}
                            }
                        },
                        "closure_reference": {
                            "input_closure_reference": {"value": ""}
                        },
                        "closure_message": {
                            "input_closure_message": {
                                "value": "Closed with priority change"
                            }
                        },
                    }
                },
                "private_metadata": json.dumps({
                    "incident_id": incident.id,
                    "carry_over": {"priority_id": str(priority_new.id)},
                }),
            },
            "user": {"id": "U123456"},
        }

        with patch(
            "firefighter.slack.views.modals.closure_reason.respond"
        ) as mock_respond:
            mock_respond.return_value = None

            result = modal.handle_modal_fn(
                ack=ack, body=body, incident=incident, user=user
            )

        assert result is True
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CLOSED
        assert incident.priority_id == priority_new.id, (
            "The priority change submitted in the Update Status modal must be "
            "applied alongside the closure."
        )

    def test_handle_modal_fn_ignores_invalid_carry_over_payload(self, mocker) -> None:
        """A malformed carry_over payload must not block closure."""
        user = UserFactory.create()
        incident = IncidentFactory.create(
            _status=IncidentStatus.INVESTIGATING,
            created_by=user,
        )

        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=mocker.PropertyMock,
            return_value=(True, []),
        )

        modal = ClosureReasonModal()
        ack = MagicMock()

        body = {
            "view": {
                "state": {
                    "values": {
                        "closure_reason": {
                            "select_closure_reason": {
                                "selected_option": {"value": ClosureReason.CANCELLED}
                            }
                        },
                        "closure_reference": {"input_closure_reference": {"value": ""}},
                        "closure_message": {
                            "input_closure_message": {"value": "ok"}
                        },
                    }
                },
                # Intentionally malformed JSON
                "private_metadata": "{not valid json",
            },
            "user": {"id": "U123456"},
        }

        with patch(
            "firefighter.slack.views.modals.closure_reason.respond"
        ) as mock_respond:
            mock_respond.return_value = None

            result = modal.handle_modal_fn(
                ack=ack, body=body, incident=incident, user=user
            )

        assert result is True
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.CLOSED


@pytest.mark.django_db
class TestExtractIncidentIdFromPrivateMetadata:
    """The incident resolver must accept both legacy and JSON private_metadata."""

    def test_legacy_plain_int(self) -> None:
        assert _extract_incident_id_from_private_metadata("42") == 42

    def test_json_with_incident_id(self) -> None:
        payload = json.dumps({"incident_id": 99, "carry_over": {"priority_id": "x"}})
        assert _extract_incident_id_from_private_metadata(payload) == 99

    def test_invalid_payload_returns_none(self) -> None:
        assert _extract_incident_id_from_private_metadata("not-json-not-int") is None

    def test_json_without_incident_id_returns_none(self) -> None:
        assert _extract_incident_id_from_private_metadata(json.dumps({"foo": "bar"})) is None
