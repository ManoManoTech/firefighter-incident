from __future__ import annotations

import logging
from copy import deepcopy
from unittest.mock import MagicMock, PropertyMock

import pytest
from pytest_mock import MockerFixture

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident import Incident
from firefighter.slack.views import CloseModal

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestCloseModal:
    @staticmethod
    def test_close_modal_build(mocker: MockerFixture) -> None:
        # Arrange
        modal = CloseModal()
        mocker.patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock(return_value=(True, [])),
        )
        incident = IncidentFactory.build()
        incident.status = IncidentStatus.MITIGATED

        # Act
        res = modal.build_modal_fn(incident=incident, body={})

        # Assert
        assert incident.can_be_closed[0] is True
        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert len(values["blocks"]) == 7

    @staticmethod
    def test_close_modal_build_initial_values(
        mocker: MockerFixture, incident: Incident
    ) -> None:
        """Test that the initial values are set correctly from the incident."""
        # Arrange
        modal = CloseModal()
        mocker.patch(
            "firefighter.incidents.models.incident.Incident.can_be_closed",
            return_value=(True, []),
            new_callable=mocker.PropertyMock,
        )
        incident.status = IncidentStatus.MITIGATED
        incident.title = "This is the title"
        incident.description = "This is the description"

        # Act
        res = modal.build_modal_fn(incident=incident, body={})
        values = res.to_dict()

        # Assert
        assert values["blocks"][1]["element"]["initial_value"] == "This is the title"
        assert (
            values["blocks"][2]["element"]["initial_value"] == "This is the description"
        )

    @staticmethod
    def test_close_modal_build_cant_close(incident: Incident) -> None:
        # Arrange
        modal = CloseModal()
        # Use MITIGATING (Mitigating) status - cannot close from this status without going through MITIGATED
        incident.status = IncidentStatus.MITIGATING

        # Act
        res = modal.build_modal_fn(incident=incident, body={})

        # Assert

        # To dict will validate the JSON as well (e.g. check the view title length)
        # Any validation error will raise an exception
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert len(values["blocks"]) >= 5
        assert (
            "This incident can't be closed yet." in values["blocks"][0]["text"]["text"]
        )

    @staticmethod
    def test_close_modal_build_shows_mitigated_status_requirement(
        mocker: MockerFixture, incident: Incident
    ) -> None:
        """Test that the modal shows STATUS_NOT_MITIGATED error with proper references.

        This test covers lines 151, 154, 159 in close.py where MITIGATED.label is used.
        """
        # Arrange
        modal = CloseModal()
        incident.status = IncidentStatus.INVESTIGATING

        # Mock requires_closure_reason to return False so we bypass the closure reason modal
        mocker.patch(
            "firefighter.slack.views.modals.utils.UpdateStatusForm.requires_closure_reason",
            return_value=False
        )

        # Mock can_be_closed to return False with STATUS_NOT_MITIGATED reason
        mocker.patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock(return_value=(False, [("STATUS_NOT_MITIGATED", "Status not mitigated")])),
        )

        # Act
        res = modal.build_modal_fn(incident=incident, body={})

        # Assert
        assert res.to_dict()
        values = res.to_dict()
        assert "blocks" in values

        # Convert blocks to text for easier searching
        blocks_text = str(values["blocks"])

        # Verify that "Mitigated" (the label) appears in the error message
        # Line 154: text=f":warning: *Status is not _{IncidentStatus.MITIGATED.label}_* :warning:\n"
        # Line 159: text=f"You can only close an incident when its status is _{IncidentStatus.MITIGATED.label}_ or _{IncidentStatus.POST_MORTEM.label}_..."
        assert "Mitigated" in blocks_text
        assert "Post-mortem" in blocks_text or "Post Mortem" in blocks_text

        # Verify the error message structure
        assert "This incident can't be closed yet." in values["blocks"][0]["text"]["text"]

    @staticmethod
    def test_close_modal_build_shows_closure_reason_from_open(incident: Incident) -> None:
        # Arrange
        modal = CloseModal()
        incident.status = IncidentStatus.OPEN

        # Act
        res = modal.build_modal_fn(incident=incident, body={})

        # Assert
        assert res.to_dict()
        values = res.to_dict()
        assert "blocks" in values
        # Should show closure reason form
        assert "Closure Reason Required" in values["blocks"][0]["text"]["text"]

    @staticmethod
    def test_submit_empty_bodied_form() -> None:
        modal = CloseModal()
        ack = MagicMock()
        user = UserFactory.build()
        with pytest.raises(TypeError, match="Expected a values dict in the body"):
            modal.handle_modal_fn(ack=ack, body={}, incident=MagicMock(), user=user)

    @staticmethod
    def test_submit_valid_form_open_incident(
        mocker: MockerFixture, incident: Incident
    ) -> None:
        incident.status = IncidentStatus.OPEN

        modal = CloseModal()
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )
        respond = mocker.patch(
            "firefighter.slack.views.modals.close.respond", return_value=None
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        modal.handle_modal_fn(
            ack=ack, body=valid_submission, user=user, incident=incident
        )

        # Assert
        ack.assert_called_once_with()
        trigger_incident_workflow.assert_not_called()
        respond.assert_called_once()

    @staticmethod
    def test_submit_valid_form_closable_incident(
        mocker: MockerFixture, incident: Incident
    ) -> None:
        modal = CloseModal()
        mocker.patch(
            "firefighter.incidents.models.incident.Incident.can_be_closed",
            return_value=(True, []),
            new_callable=mocker.PropertyMock,
        )
        incident.status = IncidentStatus.POST_MORTEM
        trigger_incident_workflow = mocker.patch.object(
            modal, "_trigger_incident_workflow"
        )

        ack = MagicMock()
        user = UserFactory.build()
        user.save()

        modal.handle_modal_fn(
            ack=ack, body=valid_submission, user=user, incident=incident
        )

        # Assert
        ack.assert_called_once_with()
        trigger_incident_workflow.assert_called_once()


valid_submission = {
    "type": "view_submission",
    "team": {"id": "T01FJ0NNFQD", "domain": "team-firefighter"},
    "user": {
        "id": "U020BFXLSKX",
        "username": "gabriel.doogabe",
        "name": "gabriel.doogabe",
        "team_id": "T01FJ0NNFQD",
    },
    "api_app_id": "A020BG97EG5",
    "token": "fake_",
    "trigger_id": "3914397216230.1528022763829.149fcfbe4712c05a4fb707c9792c2011",
    "view": {
        "id": "V03T2SMMWBV",
        "team_id": "T01FJ0NNFQD",
        "type": "modal",
        "blocks": [
            {
                "type": "input",
                "block_id": "title",
                "label": {
                    "type": "plain_text",
                    "text": "What's going on?",
                    "emoji": True,
                },
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Short, punchy description of what's happening.",
                        "emoji": True,
                    },
                    "multiline": False,
                    "min_length": 10,
                    "max_length": 128,
                    "dispatch_action_config": {
                        "trigger_actions_on": ["on_enter_pressed"]
                    },
                },
            },
            {
                "type": "input",
                "block_id": "description",
                "label": {"type": "plain_text", "text": "Summary", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Help people responding to the incident. This will be posted to #tech-incidents and on our internal status page.\nThis description can be edited later.",
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
            {
                "type": "input",
                "block_id": "severity",
                "label": {"type": "plain_text", "text": "Severity", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "static_select",
                    "action_id": "severity",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a severity",
                        "emoji": True,
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "🌦️  SEV4 - Minor issue not affecting customers.",
                            "emoji": True,
                        },
                        "value": "b814c9d2-48a8-4ac4-9c71-ff844e1b77f1",
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
                "block_id": "fTkH",
                "text": {
                    "type": "mrkdwn",
                    "text": "_<https://example.atlassian.net/wiki/spaces/INCIDENT/pages/123456>_",
                    "verbatim": False,
                },
            },
            {
                "type": "input",
                "block_id": "environment",
                "label": {"type": "plain_text", "text": "Environment", "emoji": True},
                "optional": False,
                "dispatch_action": False,
                "element": {
                    "type": "static_select",
                    "action_id": "environment",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an environment",
                        "emoji": True,
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "PRD - Production environment",
                            "emoji": True,
                        },
                        "value": "e5c46eb0-5620-4a30-81c6-4a647c189ff2",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "INT - Integration environment",
                                "emoji": True,
                            },
                            "value": "1b960430-995b-47e1-beab-23dbe3dbccbf",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "STG - Staging environment",
                                "emoji": True,
                            },
                            "value": "41e06f3b-4b42-4617-af9a-fa91e9af13c9",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "PRD - Production environment",
                                "emoji": True,
                            },
                            "value": "e5c46eb0-5620-4a30-81c6-4a647c189ff2",
                        },
                    ],
                },
            },
        ],
        "private_metadata": "",
        "callback_id": "incident_close",
        "state": {
            "values": {
                "title": {
                    "title": {"type": "plain_text_input", "value": "Valid incident"}
                },
                "description": {
                    "description": {
                        "type": "plain_text_input",
                        "value": "This is a valid description.",
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
                "severity": {
                    "severity": {
                        "type": "static_select",
                        "selected_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "🌦️  SEV4 - Minor issue not affecting customers.",
                                "emoji": True,
                            },
                            "value": "b814c9d2-48a8-4ac4-9c71-ff844e1b77f1",
                        },
                    }
                },
                "environment": {
                    "environment": {
                        "type": "static_select",
                        "selected_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "PRD - Production environment",
                                "emoji": True,
                            },
                            "value": "e5c46eb0-5620-4a30-81c6-4a647c189ff2",
                        },
                    }
                },
            }
        },
        "hash": "1660123198.SvjyXz97",
        "title": {"type": "plain_text", "text": "Close an incident", "emoji": True},
        "clear_on_close": False,
        "notify_on_close": False,
        "close": None,
        "submit": {"type": "plain_text", "text": "Close an incident", "emoji": True},
        "previous_view_id": None,
        "root_view_id": "V03T2SMMWBV",
        "app_id": "A020BG97EG5",
        "external_id": "",
        "app_installed_team_id": "T01FJ0NNFQD",
        "bot_id": "B020T8C8U9F",
    },
    "response_urls": [],
    "is_enterprise_install": False,
    "enterprise": None,
}


invalid_title = deepcopy(valid_submission)
invalid_title["view"]["state"]["values"]["title"]["title"]["value"] = "short"  # type: ignore

invalid_incident_category = deepcopy(valid_submission)
invalid_incident_category["view"]["state"]["values"]["incident_category"]["incident_category"][
    "selected_option"
]["value"] = "notauuid-d445-4fc9-92eb-e742ee14fd4a"  # type: ignore
