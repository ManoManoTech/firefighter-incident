"""Tests for ClosureReasonModal - Slack modal for closing incidents with a reason."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Priority
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
