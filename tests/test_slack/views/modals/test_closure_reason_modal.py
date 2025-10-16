"""Tests for ClosureReasonModal - Slack modal for closing incidents with a reason."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.incidents.enums import ClosureReason, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.slack.views.modals.closure_reason import ClosureReasonModal


@pytest.mark.django_db
class TestClosureReasonModalMessageTabDisabled:
    """Test ClosureReasonModal handles messages_tab_disabled gracefully."""

    def test_closure_reason_handles_messages_tab_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that messages_tab_disabled error is handled gracefully with warning log."""
        # Create test data
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(_status=IncidentStatus.INVESTIGATING, created_by=user)
        incident.save()

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
                        "closure_reference": {
                            "input_closure_reference": {"value": ""}
                        },
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

        with patch("firefighter.slack.views.modals.closure_reason.respond") as mock_respond:
            mock_respond.side_effect = SlackApiError(
                message="The request to the Slack API failed.",
                response=slack_error_response
            )

            # Execute
            result = modal.handle_modal_fn(
                ack=ack,
                body=body,
                incident=incident,
                user=user
            )

            # Assertions
            assert result is True  # Incident should still be closed successfully

            # Verify incident was closed
            incident.refresh_from_db()
            assert incident.status == IncidentStatus.CLOSED
            assert incident.closure_reason == ClosureReason.CANCELLED

            # Verify warning was logged
            assert any(
                "Cannot send DM to user" in record.message and record.levelname == "WARNING"
                for record in caplog.records
            )

    def test_closure_reason_reraises_other_slack_errors(self) -> None:
        """Test that other Slack API errors are re-raised."""
        # Create test data
        user = UserFactory.build()
        user.save()
        incident = IncidentFactory.build(_status=IncidentStatus.INVESTIGATING, created_by=user)
        incident.save()

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
                        "closure_reference": {
                            "input_closure_reference": {"value": ""}
                        },
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

        with patch("firefighter.slack.views.modals.closure_reason.respond") as mock_respond:
            mock_respond.side_effect = SlackApiError(
                message="The request to the Slack API failed.",
                response=slack_error_response
            )

            # Execute and expect exception
            with pytest.raises(SlackApiError):
                modal.handle_modal_fn(
                    ack=ack,
                    body=body,
                    incident=incident,
                    user=user
                )
