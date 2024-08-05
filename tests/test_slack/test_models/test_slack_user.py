from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from firefighter.slack.models.user import SlackUser, SlackUserManager
from firefighter.slack.slack_app import SlackApp
from tests.test_slack.conftest import MockWebClient

# Mock data for testing
mock_slack_response = {
    "user": {
        "id": "U123456",
        "name": "testuser",
        "deleted": False,
        "profile": {
            "real_name": "Test User",
            "first_name": "Test",
            "last_name": "User",
            "email": "testuser@example.com",
            "image_192": "https://example.com/image192.png",
            "image_512": "https://example.com/image512.png",
        },
        "is_bot": False,
    },
    "ok": True,
}


@pytest.fixture
def valid_user_info() -> dict[str, dict[str, Any] | Any]:
    return {
        "ok": True,
        "user": {
            "id": "U01234567",
            "name": "testuser",
            "deleted": False,
            "is_bot": False,
            "profile": {
                "real_name": "Test User",
                "first_name": "Test",
                "last_name": "User",
                "email": "testuser@example.com",
                "image_512": "https://example.com/image_512.jpg",
                "image_192": "https://example.com/image_192.jpg",
            },
        },
    }


def test_unpack_user_info() -> None:
    manager = SlackUserManager()
    unpacked_user_info = manager.unpack_user_info(mock_slack_response)

    assert unpacked_user_info["slack_id"] == "U123456"
    assert unpacked_user_info["username"] == "testuser"
    assert unpacked_user_info["first_name"] == "Test"
    assert unpacked_user_info["last_name"] == "User"
    assert unpacked_user_info["email"] == "testuser@example.com"
    assert unpacked_user_info["image"] == "https://example.com/image512.png"
    assert unpacked_user_info["deleted"] is False


@pytest.mark.django_db
def test_slack_user_link(slack_user_saved: SlackUser):
    link = slack_user_saved.link

    assert link.startswith("slack://user?team=")
    assert f"&id={slack_user_saved.slack_id}" in link


@pytest.mark.django_db
def test_update_user_info(slack_user_saved: SlackUser, mock_web_client: MockWebClient):
    slack_user = slack_user_saved

    # Mock WebClient.users_info
    mock_users_info = MagicMock(return_value=mock_slack_response)
    mock_web_client.users_info = mock_users_info
    slack_user.update_user_info(client=mock_web_client)

    # Assert that users_info was called with the correct slack_id
    mock_users_info.assert_called_once_with(user=slack_user.slack_id)

    # Assert the database values have been updated
    updated_slack_user = SlackUser.objects.get(slack_id=slack_user.slack_id)
    updated_user = updated_slack_user.user

    assert updated_slack_user.username == "testuser"
    assert updated_user.name == "Test User"
    assert updated_user.first_name == "Test"
    assert updated_user.last_name == "User"
    assert updated_user.email == "testuser@example.com"
    assert updated_user.is_active is True
    assert updated_slack_user.image == "https://example.com/image512.png"

    assert updated_slack_user.username != slack_user.username
    assert updated_user.name != slack_user.user.name
    assert updated_user.first_name != slack_user.user.first_name
    assert updated_user.last_name != slack_user.user.last_name
    assert updated_user.email != slack_user.user.email


@pytest.mark.django_db
def test_update_user_info_slack_api_error(
    slack_user_saved: SlackUser, mock_web_client: MockWebClient
):
    slack_user = slack_user_saved
    error_response = MagicMock()
    error_response.status_code = 404
    # Mock WebClient.users_info to raise a SlackApiError
    mock_users_info = MagicMock(
        side_effect=SlackApiError("SlackApiError", response=error_response)
    )
    mock_web_client.users_info = mock_users_info
    slack_user.update_user_info(client=mock_web_client)

    # Assert that users_info was called with the correct slack_id
    mock_users_info.assert_called_once_with(user=slack_user.slack_id)

    # Assert the database values have not been updated
    updated_slack_user = SlackUser.objects.get(slack_id=slack_user.slack_id)
    updated_user = updated_slack_user.user

    assert updated_slack_user.username == slack_user.username
    assert updated_user.name == slack_user.user.name
    assert updated_user.first_name == slack_user.user.first_name
    assert updated_user.last_name == slack_user.user.last_name
    assert updated_user.email == slack_user.user.email
    assert updated_user.is_active is True
    assert updated_slack_user.image == slack_user.image


@pytest.mark.django_db
def test_update_user_info_empty_response(
    slack_user_saved: SlackUser, mock_web_client: MockWebClient
):
    slack_user = slack_user_saved

    # Mock WebClient.users_info to return an empty response
    mock_users_info = MagicMock(return_value={})
    mock_web_client.users_info = mock_users_info
    slack_user.update_user_info(client=mock_web_client)

    # Assert that users_info was called with the correct slack_id
    mock_users_info.assert_called_once_with(user=slack_user.slack_id)

    # Assert the database values have not been updated
    updated_slack_user = SlackUser.objects.get(slack_id=slack_user.slack_id)
    updated_user = updated_slack_user.user

    assert updated_slack_user.username == slack_user.username
    assert updated_user.name == slack_user.user.name
    assert updated_user.first_name == slack_user.user.first_name
    assert updated_user.last_name == slack_user.user.last_name
    assert updated_user.email == slack_user.user.email
    assert updated_user.is_active is True
    assert updated_slack_user.image == slack_user.image


# Add these test functions to your test file


@pytest.mark.django_db
def test_unpack_user_info_bot(valid_user_info: dict[str, Any]):
    valid_user_info["user"]["is_bot"] = True
    unpacked_user_info = SlackUser.objects.unpack_user_info(valid_user_info)
    assert unpacked_user_info["email"] == valid_user_info["user"]["name"]
    assert unpacked_user_info["name"] == valid_user_info["user"]["profile"]["real_name"]


@pytest.mark.django_db
def test_unpack_user_info_no_image(valid_user_info):
    valid_user_info["user"]["profile"]["image_512"] = None
    valid_user_info["user"]["profile"]["image_192"] = None
    unpacked_user_info = SlackUser.objects.unpack_user_info(valid_user_info)
    assert "image" not in unpacked_user_info


@pytest.mark.django_db
def test_link(slack_user_saved: SlackUser):
    slack_user = slack_user_saved
    expected_link = (
        f"slack://user?team={SlackApp().details['team_id']}&id={slack_user.slack_id}"
    )
    assert slack_user.link == expected_link


@pytest.mark.django_db
def test_str_representation(slack_user_saved: SlackUser):
    slack_user = slack_user_saved
    assert str(slack_user) == slack_user.slack_id
