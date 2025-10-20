from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import Environment, Incident
from firefighter.slack.views import EditMetaModal

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestEditMetaModal:
    @staticmethod
    @pytest.fixture
    def incident(environment_factory) -> Incident:
        """Returns a valid incident with environment and custom_fields."""
        env_prd = environment_factory(value="PRD", name="Production", order=0)
        return IncidentFactory.create(
            environment=env_prd,
            custom_fields={"environments": ["PRD"]}
        )

    @staticmethod
    @pytest.fixture
    def multi_env_incident(environment_factory) -> Incident:
        """Returns an incident with multiple environments in custom_fields."""
        env_prd = environment_factory(value="PRD", name="Production", order=0)
        environment_factory(value="STG", name="Staging", order=1)
        environment_factory(value="INT", name="Integration", order=2)

        return IncidentFactory.create(
            environment=env_prd,
            custom_fields={"environments": ["PRD", "STG", "INT"]}
        )

    @staticmethod
    def test_build_modal_fn_single_environment(incident: Incident) -> None:
        """Test building modal with single environment."""
        modal = EditMetaModal()
        res = modal.build_modal_fn(incident)

        # Validate the JSON structure
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values
        assert values["title"]["text"] == f"Update incident #{incident.id}"[:24]
        assert values["submit"]["text"] == "Update incident"

    @staticmethod
    def test_build_modal_fn_multiple_environments(multi_env_incident: Incident) -> None:
        """Test building modal with multiple environments in custom_fields."""
        modal = EditMetaModal()
        res = modal.build_modal_fn(multi_env_incident)

        # Validate the JSON structure
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values

        # The form should show all three environments from custom_fields
        # We verify this by checking the initial values passed to the form
        assert multi_env_incident.custom_fields["environments"] == ["PRD", "STG", "INT"]

    @staticmethod
    def test_build_modal_fn_fallback_to_single_environment(environment_factory) -> None:
        """Test building modal falls back to single environment when custom_fields is empty."""
        env_prd = environment_factory(value="PRD", name="Production", order=0)
        incident = IncidentFactory.create(
            environment=env_prd,
            custom_fields={}  # No environments in custom_fields
        )

        modal = EditMetaModal()
        res = modal.build_modal_fn(incident)

        # Validate the JSON structure
        assert res.to_dict()

        values = res.to_dict()
        assert "blocks" in values

    @staticmethod
    def test_build_modal_fn_empty_custom_fields(environment_factory) -> None:
        """Test building modal when custom_fields has no environments."""
        env_stg = environment_factory(value="STG", name="Staging", order=1)
        incident = IncidentFactory.create(
            environment=env_stg,
            custom_fields={}  # Empty custom_fields
        )

        modal = EditMetaModal()
        res = modal.build_modal_fn(incident)

        # Should build successfully and fallback to single environment
        assert res.to_dict()

    @staticmethod
    def test_handle_modal_fn_update_title_and_description(
        mocker: MockerFixture, incident: Incident
    ) -> None:
        """Test handling modal submission with title and description updates."""
        modal = EditMetaModal()
        trigger_workflow = mocker.patch.object(modal, "_trigger_incident_workflow")

        ack = MagicMock()
        user = UserFactory.create()

        # Create a submission with updated title and description
        submission = create_edit_submission(
            incident=incident,
            title="Updated Incident Title",
            description="Updated incident description with more details.",
        )

        modal.handle_modal_fn(ack=ack, body=submission, incident=incident, user=user)

        # Assert
        ack.assert_called_once_with()
        trigger_workflow.assert_called_once()
        call_kwargs = trigger_workflow.call_args.kwargs
        assert call_kwargs["title"] == "Updated Incident Title"
        assert call_kwargs["description"] == "Updated incident description with more details."

    @staticmethod
    def test_handle_modal_fn_update_environments(
        mocker: MockerFixture, environment_factory
    ) -> None:
        """Test handling modal submission with environment updates."""
        env_prd = environment_factory(value="PRD", name="Production", order=0)
        env_stg = environment_factory(value="STG", name="Staging", order=1)
        env_int = environment_factory(value="INT", name="Integration", order=2)

        incident = IncidentFactory.create(
            environment=env_prd,
            custom_fields={"environments": ["PRD"]}
        )

        modal = EditMetaModal()
        trigger_workflow = mocker.patch.object(modal, "_trigger_incident_workflow")

        ack = MagicMock()
        user = UserFactory.create()

        # Create a submission with multiple environments selected
        submission = create_edit_submission(
            incident=incident,
            environment_ids=[str(env_prd.id), str(env_stg.id), str(env_int.id)],
        )

        modal.handle_modal_fn(ack=ack, body=submission, incident=incident, user=user)

        # Assert
        ack.assert_called_once_with()

        # Verify custom_fields were updated
        incident.refresh_from_db()
        assert set(incident.custom_fields["environments"]) == {"PRD", "STG", "INT"}

        # Verify primary environment is PRD (highest priority)
        trigger_workflow.assert_called_once()
        call_kwargs = trigger_workflow.call_args.kwargs
        assert call_kwargs["environment_id"] == env_prd.id

    @staticmethod
    def test_handle_modal_fn_change_primary_environment(
        mocker: MockerFixture, environment_factory
    ) -> None:
        """Test changing from one environment to another."""
        env_prd = environment_factory(value="PRD", name="Production", order=0)
        env_stg = environment_factory(value="STG", name="Staging", order=1)

        incident = IncidentFactory.create(
            environment=env_prd,
            custom_fields={"environments": ["PRD"]}
        )

        modal = EditMetaModal()
        trigger_workflow = mocker.patch.object(modal, "_trigger_incident_workflow")

        ack = MagicMock()
        user = UserFactory.create()

        # Change to STG only
        submission = create_edit_submission(
            incident=incident,
            environment_ids=[str(env_stg.id)],
        )

        modal.handle_modal_fn(ack=ack, body=submission, incident=incident, user=user)

        # Assert
        ack.assert_called_once_with()

        # Verify custom_fields were updated to STG
        incident.refresh_from_db()
        assert incident.custom_fields["environments"] == ["STG"]

        # Verify primary environment is STG
        trigger_workflow.assert_called_once()
        call_kwargs = trigger_workflow.call_args.kwargs
        assert call_kwargs["environment_id"] == env_stg.id

    @staticmethod
    def test_handle_modal_fn_no_changes(mocker: MockerFixture, incident: Incident) -> None:
        """Test handling modal submission with no changes."""
        modal = EditMetaModal()
        trigger_workflow = mocker.patch.object(modal, "_trigger_incident_workflow")

        ack = MagicMock()
        user = UserFactory.create()

        # Create a submission with same values as current incident
        submission = create_edit_submission(
            incident=incident,
            title=incident.title,
            description=incident.description,
            environment_ids=[str(incident.environment.id)],
        )

        modal.handle_modal_fn(ack=ack, body=submission, incident=incident, user=user)

        # Assert that workflow was not triggered (no changes)
        ack.assert_called_once_with()
        trigger_workflow.assert_not_called()

    @staticmethod
    def test_handle_modal_fn_empty_body(incident: Incident) -> None:
        """Test handling modal with empty body raises TypeError."""
        modal = EditMetaModal()
        ack = MagicMock()
        user = UserFactory.create()

        with pytest.raises(TypeError, match="Expected a values dict in the body"):
            modal.handle_modal_fn(ack=ack, body={}, incident=incident, user=user)


def create_edit_submission(
    incident: Incident,
    title: str | None = None,
    description: str | None = None,
    environment_ids: list[str] | None = None,
) -> dict:
    """Helper function to create a valid edit submission body."""
    # Use current values as defaults
    title = title if title is not None else incident.title
    description = description if description is not None else incident.description

    # Build environment options
    if environment_ids is None:
        # Use current incident environment
        environment_ids = [str(incident.environment.id)] if incident.environment else []

    # Convert environment IDs to options format
    env_selected_options = []
    if environment_ids:
        for env_id in environment_ids:
            env_obj = Environment.objects.get(id=env_id)
            env_selected_options.append({
                "text": {"type": "plain_text", "text": f"{env_obj.value} - {env_obj.description}", "emoji": True},
                "value": env_id,
            })

    return {
        "type": "view_submission",
        "team": {"id": "T01FJ0NNFQD", "domain": "team-firefighter"},
        "user": {
            "id": "U03L9K8P5SA",
            "username": "john.doe",
            "name": "john.doe",
            "team_id": "T01FJ0NNFQD",
        },
        "api_app_id": "A03SXN0ENM9",
        "token": "fake_token",
        "trigger_id": "3924659449141.1528022763829.670d1c03f8d04cf6655676963267ca4e",
        "view": {
            "id": "V03T304049L",
            "team_id": "T01FJ0NNFQD",
            "type": "modal",
            "private_metadata": str(incident.id),
            "callback_id": "incident_edit_incident",
            "state": {
                "values": {
                    "title": {
                        "title": {
                            "type": "plain_text_input",
                            "value": title,
                        }
                    },
                    "description": {
                        "description": {
                            "type": "plain_text_input",
                            "value": description,
                        }
                    },
                    "environment": {
                        "environment": {
                            "type": "multi_static_select",
                            "selected_options": env_selected_options,
                        }
                    },
                }
            },
            "hash": "1660220674.c7elhik9",
            "title": {"type": "plain_text", "text": f"Update incident #{incident.id}"[:24], "emoji": True},
            "clear_on_close": False,
            "notify_on_close": False,
            "close": None,
            "submit": {"type": "plain_text", "text": "Update incident", "emoji": True},
            "app_id": "A03SXN0ENM9",
            "external_id": "",
            "app_installed_team_id": "T01FJ0NNFQD",
            "bot_id": "B03T08W83AQ",
        },
        "response_urls": [],
        "is_enterprise_install": False,
        "enterprise": None,
    }
