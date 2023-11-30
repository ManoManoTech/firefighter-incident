from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
)

from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
from firefighter.incidents.models.user import User
from firefighter.slack.views.modals.open import OpeningData, OpenModal
from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails


def build_opening_data(**kwargs: Any) -> OpeningData:
    data: OpeningData = {
        "response_type": kwargs.get("response_type", "normal"),
        "impact_form_data": kwargs.get("impact_form_data", {}),
        "details_form_data": kwargs.get("details_form_data", {}),
        "incident_type": kwargs.get("incident_type", None),
    }
    return data


@pytest.fixture()
def open_incident_context() -> OpeningData:
    return build_opening_data()


@pytest.fixture()
def user() -> User:
    return User(username="testuser", email="testuser@example.com")


@pytest.fixture()
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


@pytest.mark.django_db()
def test_check_impact_form_invalid(open_incident_context: OpeningData) -> None:
    open_incident_context["impact_form_data"] = {"impact": "invalid"}  # type: ignore[dict-item]
    result = OpenModal._check_impact_form(open_incident_context)
    assert result is False


def test_validate_details_form_valid() -> None:
    details_form_modal_class = MagicMock(spec=SetIncidentDetails)
    details_form_class = MagicMock(spec=CreateIncidentFormBase)
    details_form_data = {"key": "value"}

    details_form_modal_class.form_class = details_form_class

    details_form_instance = MagicMock(spec=CreateIncidentFormBase)
    details_form_instance.is_valid.return_value = True
    details_form_class.return_value = details_form_instance

    is_valid, returned_form_class, returned_form = OpenModal._validate_details_form(
        details_form_modal_class, details_form_data
    )

    assert is_valid is True
    assert returned_form_class == details_form_class
    assert returned_form == details_form_instance


def test_validate_details_form_invalid() -> None:
    details_form_modal_class = MagicMock(spec=SetIncidentDetails)
    details_form_class = MagicMock(spec=CreateIncidentFormBase)
    details_form_data = {"key": "value"}

    details_form_modal_class.form_class = details_form_class

    details_form_instance = MagicMock(spec=CreateIncidentFormBase)
    details_form_instance.is_valid.return_value = False
    details_form_class.return_value = details_form_instance

    is_valid, returned_form_class, returned_form = OpenModal._validate_details_form(
        details_form_modal_class, details_form_data
    )

    assert is_valid is False
    assert returned_form_class == details_form_class
    assert returned_form == details_form_instance


def test_build_response_type_blocks_bis(open_incident_context: OpeningData) -> None:
    open_incident_context["response_type"] = "critical"
    blocks = OpenModal._build_response_type_blocks(open_incident_context)

    assert len(blocks) == 1
    first_block = blocks[0]
    assert isinstance(first_block, ActionsBlock)
    assert len(first_block.elements) == 2
    assert all(isinstance(element, ButtonElement) for element in first_block.elements)


@pytest.mark.django_db()
def test_build_modal_fn_empty(user: User) -> None:
    open_incident_context = OpeningData()
    view = OpenModal().build_modal_fn(open_incident_context, user=user)
    assert view.type == "modal"
    # View should only have 3 blocks
    assert len(view.blocks) == 3

    # View should not have a submit button
    assert view.submit is None
