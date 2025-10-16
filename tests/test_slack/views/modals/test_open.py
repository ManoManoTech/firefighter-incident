from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from slack_sdk.models.blocks.blocks import (
    ContextBlock,
    SectionBlock,
)

from firefighter.incidents.factories import IncidentCategoryFactory
from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
from firefighter.incidents.models.user import User
from firefighter.slack.views.modals.open import OpeningData, OpenModal
from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails


def build_opening_data(**kwargs: Any) -> OpeningData:
    data: OpeningData = {
        "response_type": kwargs.get("response_type", "normal"),
        "impact_form_data": kwargs.get("impact_form_data", {}),
        "details_form_data": kwargs.get("details_form_data", {}),
        "incident_type": kwargs.get("incident_type"),
    }
    return data


@pytest.fixture
def open_incident_context() -> OpeningData:
    return build_opening_data()


@pytest.fixture
def user() -> User:
    return User(username="testuser", email="testuser@example.com")


@pytest.fixture
def ack() -> MagicMock:
    return MagicMock()


def test_get_done_review_blocks_can_submit_false(
    open_incident_context: OpeningData, user: User
) -> None:
    blocks = OpenModal.get_done_review_blocks(
        open_incident_context,
        user,
        details_form_done=False,
        details_form_class=None,
        details_form=None,
        can_submit=False,
    )
    assert len(blocks) == 0


@pytest.mark.django_db
def test_check_impact_form_invalid(open_incident_context: OpeningData) -> None:
    open_incident_context["impact_form_data"] = {"impact": "invalid"}  # type: ignore[dict-item]
    result = OpenModal._check_impact_form(open_incident_context)
    assert result is False


def test_validate_details_form_valid() -> None:
    details_form_modal_class = MagicMock(spec=SetIncidentDetails)
    details_form_class = MagicMock(spec=CreateIncidentFormBase)
    details_form_data = {"key": "value"}
    open_incident_context = build_opening_data()

    details_form_modal_class.form_class = details_form_class

    details_form_instance = MagicMock(spec=CreateIncidentFormBase)
    details_form_instance.is_valid.return_value = True
    details_form_class.return_value = details_form_instance

    is_valid, returned_form_class, returned_form = OpenModal._validate_details_form(
        details_form_modal_class, details_form_data, open_incident_context
    )

    assert is_valid is True
    assert returned_form_class == details_form_class
    assert returned_form == details_form_instance


def test_validate_details_form_invalid() -> None:
    details_form_modal_class = MagicMock(spec=SetIncidentDetails)
    details_form_class = MagicMock(spec=CreateIncidentFormBase)
    details_form_data = {"key": "value"}
    open_incident_context = build_opening_data()

    details_form_modal_class.form_class = details_form_class

    details_form_instance = MagicMock(spec=CreateIncidentFormBase)
    details_form_instance.is_valid.return_value = False
    details_form_class.return_value = details_form_instance

    is_valid, returned_form_class, returned_form = OpenModal._validate_details_form(
        details_form_modal_class, details_form_data, open_incident_context
    )

    assert is_valid is False
    assert returned_form_class == details_form_class
    assert returned_form == details_form_instance


def test_build_response_type_blocks_bis(open_incident_context: OpeningData) -> None:
    # With no impact_form_data, should return empty list
    open_incident_context["response_type"] = "critical"
    blocks = OpenModal._build_response_type_blocks(open_incident_context)
    assert len(blocks) == 0

    # With valid impact_form_data, should return context blocks
    mock_impact_form = Mock()
    mock_impact_form.is_valid.return_value = True
    mock_impact_form.suggest_priority_from_impact.return_value = 1

    # Mock Priority object
    mock_priority = Mock()
    mock_priority.emoji = "🔴"
    mock_priority.description = "Critical"
    mock_priority.sla = "15 min"
    mock_priority.recommended_response_type = None

    open_incident_context["impact_form_data"] = {"test_field": "test_value"}

    with patch("firefighter.slack.views.modals.open.SelectImpactForm", return_value=mock_impact_form), \
         patch("firefighter.slack.views.modals.open.Priority.objects.get", return_value=mock_priority), \
         patch.object(OpenModal, "_get_impact_descriptions", return_value="Test impact"):
        blocks = OpenModal._build_response_type_blocks(open_incident_context)
        assert len(blocks) == 1
        first_block = blocks[0]
        assert isinstance(first_block, ContextBlock)


@pytest.mark.django_db
def test_build_modal_fn_empty(user: User) -> None:
    open_incident_context = OpeningData()
    view = OpenModal().build_modal_fn(open_incident_context, user=user)
    assert view.type == "modal"
    # View should only have 3 blocks
    assert len(view.blocks) == 3

    # View should not have a submit button
    assert view.submit is None


@pytest.mark.django_db
def test_get_done_review_blocks_with_custom_fields(
    user: User, priority_factory, environment_factory
) -> None:
    """Test that get_done_review_blocks doesn't crash when form has custom fields."""
    # Use factories to create DB objects
    priority = priority_factory(value=1, default=True)
    environment = environment_factory(value="PRD", default=True)
    category = IncidentCategoryFactory()

    # Create a mock form with cleaned_data containing custom fields
    mock_form = MagicMock(spec=CreateIncidentFormBase)
    mock_form.cleaned_data = {
        "title": "Test incident with custom fields",
        "description": "Testing custom fields handling",
        "priority": priority,
        "incident_category": category,
        "environment": [environment],
        "platform": ["platform-FR"],
        # Custom fields that should be removed before creating Incident
        "zendesk_ticket_id": "ZD-12345",
        "seller_contract_id": "SELLER-789",
        "zoho_desk_ticket_id": "ZOHO-456",
        "is_key_account": True,
        "is_seller_in_golden_list": False,
        "suggested_team_routing": None,
    }

    open_incident_context = build_opening_data(response_type="critical")

    # Should not raise TypeError about unexpected keyword arguments
    blocks = OpenModal.get_done_review_blocks(
        open_incident_context,
        user,
        details_form_done=True,
        details_form_class=type(mock_form),
        details_form=mock_form,
        can_submit=True,
    )

    # Should return blocks (at least the divider and tada block)
    assert len(blocks) >= 2


@pytest.mark.django_db
def test_get_done_review_blocks_critical_includes_slack_and_jira_messages(
    user: User, priority_factory, environment_factory
) -> None:
    """Test that critical incidents show both Slack channel and Jira ticket messages."""
    # Use factories to create DB objects
    priority = priority_factory(value=1, default=True)
    environment = environment_factory(value="PRD", default=True)
    category = IncidentCategoryFactory()

    # Create a mock form with cleaned_data
    mock_form = MagicMock(spec=CreateIncidentFormBase)
    mock_form.cleaned_data = {
        "title": "Test critical incident",
        "description": "Testing Slack and Jira messages",
        "priority": priority,
        "incident_category": category,
        "environment": [environment],
    }

    open_incident_context = build_opening_data(response_type="critical")

    blocks = OpenModal.get_done_review_blocks(
        open_incident_context,
        user,
        details_form_done=True,
        details_form_class=type(mock_form),
        details_form=mock_form,
        can_submit=True,
    )

    # Find the SectionBlock containing the message
    section_blocks = [block for block in blocks if isinstance(block, SectionBlock)]
    assert len(section_blocks) >= 1

    # Get the last SectionBlock which should contain the Slack + Jira message
    message_block = section_blocks[-1].text
    # Extract text string - it could be a string or a MarkdownTextObject
    assert message_block is not None, "SectionBlock text should not be None"
    message_text = message_block.text if hasattr(message_block, "text") else str(message_block)

    # Verify both Slack and Jira messages are present
    assert ":slack:" in message_text, "Slack channel message should be present for critical incidents"
    assert "A dedicated Slack channel will be created" in message_text
    assert ":jira_new:" in message_text
    assert "An associated Jira ticket will also be created" in message_text


@pytest.mark.django_db
def test_get_done_review_blocks_normal_includes_only_jira_message(
    user: User, priority_factory, environment_factory
) -> None:
    """Test that normal incidents show only Jira ticket message (no Slack channel)."""
    # Use factories to create DB objects
    priority = priority_factory(value=4, default=False)
    environment = environment_factory(value="PRD", default=True)
    category = IncidentCategoryFactory()

    # Create a mock form with cleaned_data
    mock_form = MagicMock(spec=CreateIncidentFormBase)
    mock_form.cleaned_data = {
        "title": "Test normal incident",
        "description": "Testing Jira-only message",
        "priority": priority,
        "incident_category": category,
        "environment": [environment],
    }

    open_incident_context = build_opening_data(response_type="normal")

    blocks = OpenModal.get_done_review_blocks(
        open_incident_context,
        user,
        details_form_done=True,
        details_form_class=type(mock_form),
        details_form=mock_form,
        can_submit=True,
    )

    # Find the SectionBlock containing the message
    section_blocks = [block for block in blocks if isinstance(block, SectionBlock)]
    assert len(section_blocks) >= 1

    # Get the last SectionBlock which should contain only the Jira message
    message_block = section_blocks[-1].text
    # Extract text string - it could be a string or a MarkdownTextObject
    assert message_block is not None, "SectionBlock text should not be None"
    message_text = message_block.text if hasattr(message_block, "text") else str(message_block)

    # Verify only Jira message is present (no Slack channel mention)
    assert ":slack:" not in message_text, "Slack channel message should NOT be present for normal incidents"
    assert "Slack channel" not in message_text
    assert ":jira_new:" in message_text
    assert "A Jira ticket will be created" in message_text
