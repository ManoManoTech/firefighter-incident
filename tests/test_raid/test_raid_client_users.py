from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from jira import JIRA
from pytest_mock import MockerFixture

from firefighter.incidents.models.user import User
from firefighter.jira_app.models import JiraUser
from firefighter.raid.client import RaidJiraClient


class MockJiraClient(RaidJiraClient):
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    @property
    def jira(self):
        return MockJiraAPI()


class MockJiraAPI(JIRA):
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def search_users(self, *args: Any, **kwargs: Any):
        return [Mock(raw={"accountId": "123", "emailAddress": "johndoe@example.com"})]

    def user(self, *args: Any, **kwargs: Any):
        return Mock(
            raw={
                "accountId": "123",
                "emailAddress": "johndoe@example.com",
                "displayName": "John Doe",
            }
        )


@pytest.fixture
def user() -> User:
    return User.objects.create(
        name="John Doe",
        email="johndoe@example.com",
        username="johndoe",
    )


@pytest.fixture
def not_user() -> User:
    return User.objects.create(
        name="John Does Not Exist",
        email="johndoeesnotexist@example.com",
        username="johndoeesnotexist",
    )


@pytest.fixture
def raid_client() -> MockJiraClient:
    return MockJiraClient()


@pytest.mark.django_db
def test_get_jira_user_from_user(
    raid_client: MockJiraClient, user: User, mocker: MockerFixture
):
    # Mock search_users
    raid_client.jira.search_users = Mock(
        return_value=[
            Mock(raw={"accountId": "123", "emailAddress": "johndoe@example.com"})
        ]
    )
    search_users = mocker.patch.object(raid_client.jira, "search_users")
    search_users.return_value = [
        Mock(raw={"accountId": "123", "emailAddress": "johndoe@example.com"})
    ]
    # Test when the user is valid and exists in Jira
    jira_user = raid_client.get_jira_user_from_user(user)
    assert jira_user.user.email == "johndoe@example.com"


@pytest.mark.django_db
def test_get_jira_user_from_user_in_db(
    raid_client: MockJiraClient, user: User, mocker: MockerFixture
):
    # Test when the user is valid and exists in Jira
    user.jira_user = JiraUser.objects.create(id="123", user=user)
    # Prepare no call jira.search_users(query=email_query)
    search_users = mocker.patch.object(raid_client.jira, "search_users")

    jira_user = raid_client.get_jira_user_from_user(user)
    assert jira_user.user.email == "johndoe@example.com"

    # Assert no call jira.search_users(query=email_query)
    search_users.assert_not_called()


@pytest.mark.django_db
def test_get_jira_user_from_jira_id(raid_client: MockJiraClient):
    # Test when the Jira ID is valid and exists in Jira
    jira_user = raid_client.get_jira_user_from_jira_id("123")
    assert jira_user.user.email == "johndoe@example.com"


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_user_already_exists(
    raid_client: MockJiraClient, user: User
):
    # Test when the Jira ID is valid and exists in Jira
    jira_user = raid_client.get_jira_user_from_jira_id("123")
    assert jira_user.user.email == "johndoe@example.com"


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_invalid_id(raid_client: MockJiraClient, user: User):
    with pytest.raises(ValueError, match="Jira account id is empty"):
        raid_client.get_jira_user_from_jira_id(None)  # type: ignore
    with pytest.raises(ValueError, match="Jira account id is empty"):
        raid_client.get_jira_user_from_jira_id("")
