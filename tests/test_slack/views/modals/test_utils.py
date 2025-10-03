"""Test the modal utils module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.slack.views.modals.utils import (
    get_close_modal_view,
    handle_close_modal_callback,
    handle_update_status_close_request,
)


@pytest.mark.django_db
class TestModalUtils:
    """Test modal utility functions."""

    def test_get_close_modal_view_requires_reason(self):
        """Test get_close_modal_view when closure reason is required."""
        # Create incident in OPEN status (requires closure reason)
        incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        body = {}

        with patch("firefighter.slack.views.modals.utils.UpdateStatusForm.requires_closure_reason", return_value=True), \
             patch("firefighter.slack.views.modals.utils.modal_closure_reason.build_modal_fn") as mock_build:
            mock_build.return_value = MagicMock()

            result = get_close_modal_view(body, incident)

            assert result is not None
            mock_build.assert_called_once_with(body, incident)

    def test_get_close_modal_view_no_reason_required(self):
        """Test get_close_modal_view when closure reason is not required."""
        # Create incident in POST_MORTEM status (doesn't require closure reason)
        incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        body = {}

        with patch("firefighter.slack.views.modals.utils.UpdateStatusForm.requires_closure_reason", return_value=False):
            result = get_close_modal_view(body, incident)

            assert result is None

    def test_handle_close_modal_callback_closure_reason(self):
        """Test handle_close_modal_callback for closure reason modal."""
        incident = IncidentFactory.create()
        user = MagicMock()
        ack = MagicMock()

        body = {
            "view": {
                "callback_id": "incident_closure_reason"
            }
        }

        with patch("firefighter.slack.views.modals.utils.modal_closure_reason.handle_modal_fn") as mock_handle:
            mock_handle.return_value = True

            result = handle_close_modal_callback(ack, body, incident, user)

            assert result is True
            mock_handle.assert_called_once_with(ack, body, incident, user)

    def test_handle_close_modal_callback_normal_modal(self):
        """Test handle_close_modal_callback for normal close modal."""
        incident = IncidentFactory.create()
        user = MagicMock()
        ack = MagicMock()

        body = {
            "view": {
                "callback_id": "incident_close"  # Not closure reason
            }
        }

        result = handle_close_modal_callback(ack, body, incident, user)

        assert result is None

    def test_handle_update_status_close_request_requires_reason(self):
        """Test handle_update_status_close_request when reason is required."""
        incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        ack = MagicMock()
        body = {}
        target_status = IncidentStatus.CLOSED

        with patch("firefighter.slack.views.modals.utils.UpdateStatusForm.requires_closure_reason", return_value=True), \
             patch("firefighter.slack.views.modals.utils.modal_closure_reason.build_modal_fn") as mock_build:
            mock_build.return_value = MagicMock()

            result = handle_update_status_close_request(ack, body, incident, target_status)

            assert result is True
            ack.assert_called_once_with(response_action="push", view=mock_build.return_value)
            mock_build.assert_called_once_with(body, incident)

    def test_handle_update_status_close_request_no_reason_required(self):
        """Test handle_update_status_close_request when reason is not required."""
        incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)
        ack = MagicMock()
        body = {}
        target_status = IncidentStatus.CLOSED

        with patch("firefighter.slack.views.modals.utils.UpdateStatusForm.requires_closure_reason", return_value=False):
            result = handle_update_status_close_request(ack, body, incident, target_status)

            assert result is False
            ack.assert_not_called()

    def test_handle_update_status_close_request_non_close_status(self):
        """Test handle_update_status_close_request for non-close status."""
        incident = IncidentFactory.create()
        ack = MagicMock()
        body = {}
        target_status = IncidentStatus.INVESTIGATING

        result = handle_update_status_close_request(ack, body, incident, target_status)

        assert result is False
        ack.assert_not_called()

    def test_handle_close_modal_callback_missing_view(self):
        """Test handle_close_modal_callback with missing view in body."""
        incident = IncidentFactory.create()
        user = MagicMock()
        ack = MagicMock()

        body = {}  # No view key

        result = handle_close_modal_callback(ack, body, incident, user)

        assert result is None
