from __future__ import annotations

import logging
from unittest.mock import MagicMock, PropertyMock

import pytest
from django.conf import settings
from pytest_mock import MockerFixture

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Incident
from firefighter.slack.views import UpdateStatusModal

logger = logging.getLogger(__name__)
SLACK_SEVERITY_HELP_GUIDE_URL = settings.SLACK_SEVERITY_HELP_GUIDE_URL


@pytest.mark.django_db
class TestUpdateStatusModal:
    @staticmethod
    @pytest.fixture
    def incident() -> Incident:
        """Returns a valid incident."""
        return IncidentFactory.build()

    @staticmethod
    def test_update_status_modal_build(incident: Incident) -> None:
        modal = UpdateStatusModal()
        res = modal.build_modal_fn(incident)

        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        # If link, to doc, additionnal block
        blocks_count = 7 if SLACK_SEVERITY_HELP_GUIDE_URL else 6
        assert len(values["blocks"]) == blocks_count

    @staticmethod
    def test_submit_empty_bodied_form(incident: Incident) -> None:
        modal = UpdateStatusModal()
        ack = MagicMock()
        user = UserFactory.build()
        with pytest.raises(TypeError, match="Expected a values dict in the body"):
            modal.handle_modal_fn(ack=ack, body={}, incident=incident, user=user)

    @staticmethod
    def test_submit_valid_form(mocker: MockerFixture) -> None:
        # Create an incident in OPEN status so we can transition to INVESTIGATING
        incident = IncidentFactory.build(_status=IncidentStatus.OPEN)  # OPEN status

        modal = UpdateStatusModal()
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        # Create a valid submission that transitions from OPEN to INVESTIGATING (valid workflow)
        valid_submission_copy = dict(valid_submission)
        # Change status to INVESTIGATING (20) which is valid from OPEN
        valid_submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Investigating", "emoji": True},
            "value": "20",
        }

        modal.handle_modal_fn(
            ack=ack, body=valid_submission_copy, incident=incident, user=user
        )

        # Assert
        ack.assert_called_once_with()
        trigger_incident_workflow.assert_called_once()

    @staticmethod
    def test_cannot_close_without_required_key_events(mocker: MockerFixture) -> None:
        """Test that closing is prevented when required key events are missing.

        This tests the scenario where a P3+ incident (no postmortem needed) is in
        MITIGATED status and tries to close, but missing key events blocks it.
        """
        # Create a user first
        user = UserFactory.build()
        user.save()

        # Create a P3+ incident in MITIGATED status (can go directly to CLOSED)
        incident = IncidentFactory.build(
            _status=IncidentStatus.MITIGATED,
            created_by=user,
        )
        incident.save()
        # Mock needs_postmortem to return False (P3+ incident)
        mocker.patch.object(
            type(incident),
            "needs_postmortem",
            new_callable=PropertyMock,
            return_value=False
        )
        # Mock can_be_closed to return False with MISSING_REQUIRED_KEY_EVENTS reason
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("MISSING_REQUIRED_KEY_EVENTS", "Missing key events: detected, started")])
        )

        modal = UpdateStatusModal()
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        # Create a submission trying to close the incident
        submission_copy = dict(valid_submission)
        # Change status to CLOSED (60)
        submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Closed", "emoji": True},
            "value": "60",
        }
        # Update the private_metadata to match our test incident
        submission_copy["view"]["private_metadata"] = str(incident.id)

        modal.handle_modal_fn(
            ack=ack, body=submission_copy, incident=incident, user=user
        )

        # Assert that ack was called with errors (may be 1 or 2 calls depending on form validation)
        assert ack.called
        # Check the last call (the error response)
        last_call_kwargs = ack.call_args.kwargs
        assert "response_action" in last_call_kwargs
        assert last_call_kwargs["response_action"] == "errors"
        assert "errors" in last_call_kwargs
        assert "status" in last_call_kwargs["errors"]
        # Check that the error message mentions the missing key events
        error_msg = last_call_kwargs["errors"]["status"]
        assert "Cannot close this incident" in error_msg
        assert "Missing key events" in error_msg

        # Verify that incident update was NOT triggered
        trigger_incident_workflow.assert_not_called()

    @staticmethod
    def test_cannot_close_from_postmortem_without_key_events(mocker: MockerFixture) -> None:
        """Test that closing from POST_MORTEM is prevented when key events missing.

        This tests a P1/P2 incident in POST_MORTEM trying to close but blocked
        by missing key events.
        """
        # Create a user first
        user = UserFactory.build()
        user.save()

        # Create a P1/P2 incident in POST_MORTEM status
        incident = IncidentFactory.build(
            _status=IncidentStatus.POST_MORTEM,
            created_by=user,
        )
        incident.save()
        # Mock can_be_closed to return False with MISSING_REQUIRED_KEY_EVENTS reason
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("MISSING_REQUIRED_KEY_EVENTS", "Missing key events: detected, started")])
        )

        modal = UpdateStatusModal()
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        # Create a submission trying to close the incident
        submission_copy = dict(valid_submission)
        submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Closed", "emoji": True},
            "value": "60",
        }
        submission_copy["view"]["private_metadata"] = str(incident.id)

        modal.handle_modal_fn(
            ack=ack, body=submission_copy, incident=incident, user=user
        )

        # Assert that ack was called with errors
        assert ack.called
        last_call_kwargs = ack.call_args.kwargs
        assert "response_action" in last_call_kwargs
        assert last_call_kwargs["response_action"] == "errors"
        assert "errors" in last_call_kwargs
        assert "status" in last_call_kwargs["errors"]
        error_msg = last_call_kwargs["errors"]["status"]
        assert "Cannot close this incident" in error_msg
        assert "Missing key events" in error_msg

        # Verify that incident update was NOT triggered
        trigger_incident_workflow.assert_not_called()

    @staticmethod
    def test_cannot_close_p1_p2_without_postmortem(mocker: MockerFixture, priority_factory, environment_factory) -> None:
        """Test that P1/P2 incidents in PRD cannot be closed directly from INVESTIGATING.

        For P1/P2 incidents requiring post-mortem, although the form allows CLOSED as an option
        from INVESTIGATING status, the can_be_closed validation should prevent closure with
        an error message about needing to go through post-mortem.
        """
        # Create a user first
        user = UserFactory.build()
        user.save()

        # Create P1 priority (needs_postmortem=True) and PRD environment
        p1_priority = priority_factory(value=1, name="P1", needs_postmortem=True)
        prd_environment = environment_factory(value="PRD", name="Production")

        # Create a P1/P2 incident in INVESTIGATING status
        # From INVESTIGATING, the form allows transitioning to CLOSED (but can_be_closed will block it)
        incident = IncidentFactory.build(
            _status=IncidentStatus.INVESTIGATING,
            created_by=user,
            priority=p1_priority,
            environment=prd_environment,
        )
        incident.save()
        # Mock can_be_closed to return False with STATUS_NOT_POST_MORTEM reason
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("STATUS_NOT_POST_MORTEM", "Incident is not in PostMortem status, and needs one because of its priority and environment (P1/PRD).")])
        )

        modal = UpdateStatusModal()

        # Mock handle_update_status_close_request to NOT show closure reason modal
        # This allows the test to reach the can_be_closed validation
        mocker.patch(
            "firefighter.slack.views.modals.update_status.handle_update_status_close_request",
            return_value=False
        )

        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        # Create a submission trying to close the incident
        submission_copy = dict(valid_submission)
        submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Closed", "emoji": True},
            "value": "60",
        }
        submission_copy["view"]["private_metadata"] = str(incident.id)

        modal.handle_modal_fn(
            ack=ack, body=submission_copy, incident=incident, user=user
        )

        # Assert that ack was called with errors
        assert ack.called
        last_call_kwargs = ack.call_args.kwargs
        assert "response_action" in last_call_kwargs
        assert last_call_kwargs["response_action"] == "errors"
        assert "errors" in last_call_kwargs
        assert "status" in last_call_kwargs["errors"]
        error_msg = last_call_kwargs["errors"]["status"]
        assert "Cannot close this incident" in error_msg
        assert "PostMortem status" in error_msg

        # Verify that incident update was NOT triggered
        trigger_incident_workflow.assert_not_called()

    @staticmethod
    def test_closure_reason_modal_shown_when_closing_from_investigating(mocker: MockerFixture) -> None:
        """Test that closure reason modal is shown when trying to close from INVESTIGATING.

        This tests that handle_update_status_close_request correctly shows the
        closure reason modal and returns True, blocking the normal closure flow.
        """
        # Create an incident in INVESTIGATING status
        incident = IncidentFactory.build(
            _status=IncidentStatus.INVESTIGATING,
        )

        modal = UpdateStatusModal()

        # Mock handle_update_status_close_request to return True (modal shown)
        mock_handle_close = mocker.patch(
            "firefighter.slack.views.modals.update_status.handle_update_status_close_request",
            return_value=True
        )

        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        # Create a submission trying to close the incident
        submission_copy = dict(valid_submission)
        submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Closed", "emoji": True},
            "value": "60",
        }
        submission_copy["view"]["private_metadata"] = str(incident.id)

        modal.handle_modal_fn(
            ack=ack, body=submission_copy, incident=incident, user=user
        )

        # Verify handle_update_status_close_request was called
        mock_handle_close.assert_called_once_with(ack, submission_copy, incident, IncidentStatus.CLOSED)

        # Verify that incident update was NOT triggered (because closure reason modal was shown)
        trigger_incident_workflow.assert_not_called()

    @staticmethod
    def test_can_close_when_all_conditions_met(mocker: MockerFixture) -> None:
        """Test that closing is allowed when all conditions are met."""
        # Create a user first
        user = UserFactory.build()
        user.save()

        # Create an incident in MITIGATED status with all conditions met
        incident = IncidentFactory.build(
            _status=IncidentStatus.MITIGATED,
            created_by=user,
        )
        # IMPORTANT: Save the incident so it has an ID for the form to reference
        incident.save()

        # Mock can_be_closed to return True (all conditions met)
        mocker.patch.object(
            type(incident),
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(True, [])
        )

        modal = UpdateStatusModal()
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()

        # Create a submission to close the incident
        submission_copy = dict(valid_submission)
        submission_copy["view"]["state"]["values"]["status"]["status"]["selected_option"] = {
            "text": {"type": "plain_text", "text": "Closed", "emoji": True},
            "value": "60",
        }
        submission_copy["view"]["private_metadata"] = str(incident.id)

        modal.handle_modal_fn(
            ack=ack, body=submission_copy, incident=incident, user=user
        )

        # Assert that ack was called successfully (no errors)
        # The first call is the successful ack() without errors
        first_call_kwargs = ack.call_args_list[0][1] if ack.call_args_list else ack.call_args.kwargs
        assert first_call_kwargs == {} or "errors" not in first_call_kwargs

        # Verify that incident update WAS triggered
        trigger_incident_workflow.assert_called_once()


valid_submission = {
    "type": "view_submission",
    "team": {"id": "T01FJ0NNFQD", "domain": "team-firefighter"},
    "user": {
        "id": "U03L9K8P5SA",
        "username": "john.doe",
        "name": "john.doe",
        "team_id": "T01FJ0NNFQD",
    },
    "api_app_id": "A03SXN0ENM9",
    "token": "fake_",
    "trigger_id": "3924659449141.1528022763829.670d1c03f8d04cf6655676963267ca4e",
    "view": {
        "id": "V03T304049L",
        "team_id": "T01FJ0NNFQD",
        "type": "modal",
        "blocks": [
            {
                "type": "input",
                "block_id": "message",
                "label": {
                    "type": "plain_text",
                    "text": "Update message",
                    "emoji": True,
                },
                "optional": True,
                "dispatch_action": False,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "message",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Please describe the new status for the incident.\nE.g: Fixed with instance reboot.",
                        "emoji": True,
                    },
                    "multiline": True,
                    "min_length": 10,
                    "max_length": 1200,
                    "dispatch_action_config": {
                        "trigger_actions_on": ["on_enter_pressed"]
                    },
                },
            },
            {
                "type": "input",
                "block_id": "status",
                "label": {"type": "plain_text", "text": "Status", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "static_select",
                    "action_id": "status",
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Open", "emoji": True},
                        "value": "10",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Open",
                                "emoji": True,
                            },
                            "value": "10",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Investigating",
                                "emoji": True,
                            },
                            "value": "20",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Mitigating",
                                "emoji": True,
                            },
                            "value": "30",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Mitigated",
                                "emoji": True,
                            },
                            "value": "40",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Post-mortem",
                                "emoji": True,
                            },
                            "value": "50",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Closed",
                                "emoji": True,
                            },
                            "value": "60",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "priority",
                "label": {"type": "plain_text", "text": "Priority", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "static_select",
                    "action_id": "priority",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a priority",
                        "emoji": True,
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "🌩️  SEV3 - Minor issue affecting customers.",
                            "emoji": True,
                        },
                        "value": "e12c3836-ea9b-44bf-a3cf-5a715d62395b",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🌪️  SEV1 - Critical issue that warrants liaison with e-team.",
                                "emoji": True,
                            },
                            "value": "3d8a4e0f-cc79-4063-9431-8aa785a56ca0",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "⛈️  SEV2 - Major issue impacting customers.",
                                "emoji": True,
                            },
                            "value": "8ab02fa9-f950-49cb-982e-b8d653e38ffc",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🌩️  SEV3 - Minor issue affecting customers.",
                                "emoji": True,
                            },
                            "value": "e12c3836-ea9b-44bf-a3cf-5a715d62395b",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🌦️  SEV4 - Minor issue not affecting customers.",
                                "emoji": True,
                            },
                            "value": "b814c9d2-48a8-4ac4-9c71-ff844e1b77f1",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🐞  SEV5 - Cosmetic issue not affecting customers.",
                                "emoji": True,
                            },
                            "value": "e57c2084-d7e0-4dea-9f6b-a4e8bc5a55d4",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🤡  GAMEDAY - Gamedays experiments",
                                "emoji": True,
                            },
                            "value": "701d498c-067f-43cd-b1ca-0977d983f27e",
                        },
                    ],
                },
            },
            {
                "type": "section",
                "block_id": "rgw",
                "text": {
                    "type": "mrkdwn",
                    "text": "_<https://example.atlassian.net/wiki/spaces/INCIDENT/pages/123456/>_",
                    "verbatim": False,
                },
            },
            {
                "type": "input",
                "block_id": "incident_category",
                "label": {"type": "plain_text", "text": "Issue category", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "static_select",
                    "action_id": "incident_category",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select affected issue category",
                        "emoji": True,
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "Back Office",
                            "emoji": True,
                        },
                        "value": "43b582f1-d445-4fc9-92eb-e742ee14fd4a",
                    },
                    "option_groups": [
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Tech Platform",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Back Office",
                                        "emoji": True,
                                    },
                                    "value": "43b582f1-d445-4fc9-92eb-e742ee14fd4a",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "CDN",
                                        "emoji": True,
                                    },
                                    "value": "962bf559-5fc2-4cd4-8834-6c3c1e767085",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Data Factory",
                                        "emoji": True,
                                    },
                                    "value": "63a9d7d7-6df7-4771-8ad1-a53d2a78951f",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Infrastructure",
                                        "emoji": True,
                                    },
                                    "value": "5abb78d3-1214-4a06-81a1-04351a5c9b33",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "QA",
                                        "emoji": True,
                                    },
                                    "value": "79fa2929-d44f-4c4e-862f-e8d50fa9d5b2",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Visitors",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "B2C Advice",
                                        "emoji": True,
                                    },
                                    "value": "18ac3799-4559-4a50-8964-c89f475265fe",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "B2C Retention",
                                        "emoji": True,
                                    },
                                    "value": "a218d573-4cc9-4862-8eb1-800f826a2f9c",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Search",
                                        "emoji": True,
                                    },
                                    "value": "8434e40e-66e3-4255-ba42-652d5af078c0",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Spartacux",
                                        "emoji": True,
                                    },
                                    "value": "421927b9-76a2-43b3-9a44-92e794b5c523",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Buyers",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Customer Invoicing",
                                        "emoji": True,
                                    },
                                    "value": "e1d539ce-e02b-47fa-b16c-39d26e3ddf9c",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Customer Management",
                                        "emoji": True,
                                    },
                                    "value": "2f8a8cad-4950-41b3-8fb3-ec0b6608f324",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Inventory",
                                        "emoji": True,
                                    },
                                    "value": "4ef370d3-73dc-4ea6-829b-4cd155abaa93",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Shopping Cart",
                                        "emoji": True,
                                    },
                                    "value": "d81c2362-f44c-4e2c-a431-6a5e1c53415b",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Sellers",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Ads management",
                                        "emoji": True,
                                    },
                                    "value": "189daae3-1391-4f84-9aaf-72c587df810e",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "HUB",
                                        "emoji": True,
                                    },
                                    "value": "fb50fa59-4d7f-42ea-99e3-412f63fd91bd",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Sellers Animation",
                                        "emoji": True,
                                    },
                                    "value": "4c896455-f6d8-42c8-b6cf-d5be87cdfc3c",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Sellers Management",
                                        "emoji": True,
                                    },
                                    "value": "89a1798d-b03e-4d36-aa26-b9a7e22379a1",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Toolbox",
                                        "emoji": True,
                                    },
                                    "value": "26dbf9e7-4f09-4f12-a77c-bfb7cc426804",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Product Catalog",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Product Catalog",
                                        "emoji": True,
                                    },
                                    "value": "276be9a2-8ac2-4a84-9ba8-39a4244bfc0b",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Product Delivery",
                                        "emoji": True,
                                    },
                                    "value": "6e4ce13e-527d-426a-a753-36c5f207a8bb",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Product Discovery",
                                        "emoji": True,
                                    },
                                    "value": "86ae1442-a15a-4545-98bb-1a3226b98a23",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Product Feed",
                                        "emoji": True,
                                    },
                                    "value": "3d71d900-bf53-47e2-883b-332c641f7541",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Product Offer  Management",
                                        "emoji": True,
                                    },
                                    "value": "6a0e0920-c67e-451d-8189-bb5d01baf797",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Pro",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Pro Animation",
                                        "emoji": True,
                                    },
                                    "value": "36444a95-6194-4873-8805-0aa4f0e3d5b1",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Pro Management",
                                        "emoji": True,
                                    },
                                    "value": "46fea112-5861-467e-b3d9-50911fe6d567",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Pro Services",
                                        "emoji": True,
                                    },
                                    "value": "b7d8176c-c2d6-4165-9cff-e1edec16bec4",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Finance Operations",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Payment",
                                        "emoji": True,
                                    },
                                    "value": "02a18a9c-67ba-45e8-9b50-8662f1c6eae1",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Seller Finance Operations",
                                        "emoji": True,
                                    },
                                    "value": "59067b04-bf1c-4280-b780-19fd81a236bb",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Sellers Billing",
                                        "emoji": True,
                                    },
                                    "value": "6c63ca62-3b5a-4b68-976b-f396881d84df",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Traffic Acquisition",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Affiliation",
                                        "emoji": True,
                                    },
                                    "value": "f28a2d22-fa77-4d33-8b78-30e3a1828c5e",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Free Acquisition",
                                        "emoji": True,
                                    },
                                    "value": "22e1e81d-d995-435c-9138-4bc721f08a02",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Paid Acquisition",
                                        "emoji": True,
                                    },
                                    "value": "44cfd60f-c904-4e46-a3c9-dab977d0321e",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "SEO",
                                        "emoji": True,
                                    },
                                    "value": "f6f05447-4444-4abb-88b6-728493de19fa",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Mobile",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Mobile B2C Apps",
                                        "emoji": True,
                                    },
                                    "value": "0b7df3de-e3b5-4924-bcff-bb0ccc31fa03",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Mobile PRO Apps",
                                        "emoji": True,
                                    },
                                    "value": "a654d411-4962-48d0-a2b0-7162f82d9c73",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Order",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Customer Order",
                                        "emoji": True,
                                    },
                                    "value": "7529a8b4-ec9b-4722-a772-e10ff7a616ad",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Purchase Order",
                                        "emoji": True,
                                    },
                                    "value": "0c6eafc4-030d-406b-857d-457626a03d25",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Seller Order",
                                        "emoji": True,
                                    },
                                    "value": "eef1c9d0-a460-4821-8dc7-6361ba1e016c",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Validate Order",
                                        "emoji": True,
                                    },
                                    "value": "e64edcbf-1908-49fe-82d7-6c2e4d4b54f4",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Security",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Attack",
                                        "emoji": True,
                                    },
                                    "value": "0dff9974-b5bd-4d3d-84a0-b93b8d3a69ce",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Security Misc",
                                        "emoji": True,
                                    },
                                    "value": "89c9ff50-5b0b-4554-a3e3-cbe31258dd19",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "System Compromise",
                                        "emoji": True,
                                    },
                                    "value": "8bfafb93-8790-42f0-898a-d2e30e8ba532",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Care",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Customer Care",
                                        "emoji": True,
                                    },
                                    "value": "f460e4ee-ac13-4b94-b9e4-fbb0aa87558c",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Internal Messaging",
                                        "emoji": True,
                                    },
                                    "value": "de920235-2c36-45fc-b366-02e9079603b2",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Sysadmin",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Applications",
                                        "emoji": True,
                                    },
                                    "value": "0f2c7343-d526-4aee-8b54-ef1de7c1fd61",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Infra - System",
                                        "emoji": True,
                                    },
                                    "value": "3e0bedcb-725b-4c02-876f-c7665d5bb15d",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Network",
                                        "emoji": True,
                                    },
                                    "value": "c419c3a0-9490-416e-8b4c-4e39c55b41a8",
                                },
                            ],
                        },
                        {
                            "label": {
                                "type": "plain_text",
                                "text": "Other",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Legal",
                                        "emoji": True,
                                    },
                                    "value": "5900badb-1d82-4aa6-b6e2-b76f29a83d5f",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Manomano",
                                        "emoji": True,
                                    },
                                    "value": "432e2ea4-4908-484b-8fa8-2bd943cff41f",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Other",
                                        "emoji": True,
                                    },
                                    "value": "390a993a-d273-4db8-b7d6-190ab294961a",
                                },
                            ],
                        },
                    ],
                },
            },
            {"type": "divider", "block_id": "fw55u"},
            {
                "type": "context",
                "block_id": "9Ki",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":fire_engine:  Firefighter dev",
                        "verbatim": False,
                    }
                ],
            },
        ],
        "private_metadata": "1",
        "callback_id": "incident_update_status",
        "state": {
            "values": {
                "message": {"message": {"type": "plain_text_input", "value": None}},
                "status": {
                    "status": {
                        "type": "static_select",
                        "selected_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "Open",
                                "emoji": True,
                            },
                            "value": "10",
                        },
                    }
                },
                "priority": {
                    "priority": {
                        "type": "static_select",
                        "selected_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "🌩️  SEV3 - Minor issue affecting customers.",
                                "emoji": True,
                            },
                            "value": "e12c3836-ea9b-44bf-a3cf-5a715d62395b",
                        },
                    }
                },
                "incident_category": {
                    "incident_category": {
                        "type": "static_select",
                        "selected_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "Back Office",
                                "emoji": True,
                            },
                            "value": "43b582f1-d445-4fc9-92eb-e742ee14fd4a",
                        },
                    }
                },
            }
        },
        "hash": "1660220674.c7elhik9",
        "title": {"type": "plain_text", "text": "Update incident #1", "emoji": True},
        "clear_on_close": False,
        "notify_on_close": False,
        "close": None,
        "submit": {"type": "plain_text", "text": "Update incident", "emoji": True},
        "previous_view_id": "V03T6KCK9JR",
        "root_view_id": "V03T6KCK9JR",
        "app_id": "A03SXN0ENM9",
        "external_id": "",
        "app_installed_team_id": "T01FJ0NNFQD",
        "bot_id": "B03T08W83AQ",
    },
    "response_urls": [],
    "is_enterprise_install": False,
    "enterprise": None,
}
