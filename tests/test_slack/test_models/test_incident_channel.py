from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models import User
from firefighter.incidents.models.incident import Incident
from firefighter.slack.factories import SlackUserFactory
from firefighter.slack.models.conversation import ConversationStatus
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.models.user import SlackUser
from firefighter.slack.utils import channel_name_from_incident
from tests.test_slack.conftest import MockWebClient


@pytest.fixture
def users_mapped() -> list[User]:
    return UserFactory.create_batch(5)


@pytest.mark.django_db
def test_get_active_slack_users(
    incident_channel: IncidentChannel, users_mapped: list[User]
):
    with patch.object(
        SlackUser.objects, "add_slack_id_to_user"
    ) as mock_add_slack_id_to_user:
        mock_add_slack_id_to_user.side_effect = lambda user: (
            user if user.is_active else None
        )

        for i, user in enumerate(users_mapped):
            user.is_active = i % 2 == 0  # set every second user as inactive

        active_users = incident_channel._get_active_slack_users(users_mapped)

        assert len(active_users) == 3  # only 3 out of 5 users are active
        assert all(user.is_active for user in active_users)


@pytest.mark.django_db
def test_get_slack_id_list(incident_channel: IncidentChannel, users_mapped: list[User]):
    slack_ids = {f"slack_id{i}" for i in range(len(users_mapped))}
    for user, slack_id in zip(users_mapped, slack_ids, strict=True):
        user.slack_user = SlackUser()
        user.slack_user.slack_id = slack_id

    retrieved_slack_ids = incident_channel._get_slack_id_list(users_mapped)

    assert retrieved_slack_ids == slack_ids


@pytest.mark.django_db
def test_invite_users_with_slack_id(
    incident_channel: IncidentChannel,
    users_mapped: list[User],
    mock_web_client: MockWebClient,
):
    incident_channel.channel_id = "test_channel"
    user_slack_ids = {f"user{i}" for i in range(len(users_mapped))}

    mock_web_client.conversations_invite.return_value = {"ok": True}

    invited_slack_ids = incident_channel._invite_users_with_slack_id(
        user_slack_ids, mock_web_client
    )

    assert invited_slack_ids == user_slack_ids
    mock_web_client.conversations_invite.assert_called_once_with(
        channel=incident_channel.channel_id, users=list(user_slack_ids)
    )


@pytest.mark.django_db
def test_invite_users_to_conversation_individually(
    incident_channel: IncidentChannel,
    users_mapped: list[User],
    mock_web_client: WebClient,
) -> None:
    incident_channel.channel_id = "test_channel"
    user_slack_ids = {f"user{i}" for i in range(len(users_mapped))}

    # Mock the _invite_users_with_slack_id method to raise exception for specific users
    with patch.object(
        incident_channel, "_invite_users_with_slack_id", autospec=True
    ) as mock_invite_users:
        mock_invite_users.side_effect = lambda user_ids, client: (  # noqa: ARG005
            user_ids if "user1" in user_ids else SlackApiError
        )

        invited_slack_ids = incident_channel._invite_users_to_conversation_individually(
            user_slack_ids, mock_web_client
        )
        assert mock_invite_users.call_count == len(
            user_slack_ids
        )  # all users were attempted to be invited
        # All users where invited
        assert invited_slack_ids == user_slack_ids


@pytest.mark.django_db
def test_invite_users_to_conversation_individually_single_failure(
    incident_channel: IncidentChannel,
    users_mapped: list[User],
    mock_web_client: MockWebClient,
) -> None:
    incident_channel.channel_id = "test_channel"
    user_slack_ids = {f"user{i}" for i in range(len(users_mapped))}

    # Assume user1 fails to be invited
    failed_user = "user1"

    # Mock the _invite_users_with_slack_id method to raise exception for one user
    def side_effect(args: Any, kwargs: Any) -> Any:
        if failed_user in args:
            raise SlackApiError("error", MagicMock(spec=SlackResponse))
        return args

    with patch.object(
        incident_channel,
        "_invite_users_with_slack_id",
        autospec=True,
        side_effect=side_effect,
    ) as mock_invite_users:
        invited_slack_ids = incident_channel._invite_users_to_conversation_individually(
            user_slack_ids, mock_web_client
        )

        assert invited_slack_ids == user_slack_ids - {
            failed_user
        }  # all users except one were invited successfully
        assert mock_invite_users.call_count == len(
            user_slack_ids
        )  # individual invite was called once for each user


@pytest.mark.django_db
def test_invite_users_to_conversation_batch_success(
    incident_channel: IncidentChannel,
    users_mapped: list[User],
    mock_web_client: MockWebClient,
) -> None:
    incident_channel.channel_id = "test_channel"
    user_slack_ids = {f"user{i}" for i in range(len(users_mapped))}

    # Mock the _invite_users_with_slack_id method to succeed for all users
    with patch.object(
        incident_channel, "_invite_users_with_slack_id", autospec=True
    ) as mock_invite_users:
        mock_invite_users.return_value = user_slack_ids

        invited_slack_ids = incident_channel._invite_users_to_conversation(
            user_slack_ids, mock_web_client
        )

        assert (
            invited_slack_ids == user_slack_ids
        )  # all users were invited successfully
        mock_invite_users.assert_called_once_with(
            user_slack_ids, mock_web_client
        )  # batch invite was called once


@pytest.mark.django_db
def test_invite_users_to_conversation_batch_fail(
    incident_channel: IncidentChannel,
    users_mapped: list[User],
    mock_web_client: MockWebClient,
):
    incident_channel.channel_id = "test_channel"
    user_slack_ids = {f"user{i}" for i in range(len(users_mapped))}

    # Mock the _invite_users_with_slack_id method to raise exception for all users
    with patch.object(
        incident_channel, "_invite_users_with_slack_id", autospec=True
    ) as mock_invite_users:
        mock_invite_users.side_effect = SlackApiError(
            "error", MagicMock(spec=SlackResponse)
        )

        # Mock the _invite_users_to_conversation_individually method to succeed for all users
        with patch.object(
            incident_channel,
            "_invite_users_to_conversation_individually",
            autospec=True,
        ) as mock_invite_individual:
            mock_invite_individual.return_value = user_slack_ids

            invited_slack_ids = incident_channel._invite_users_to_conversation(
                user_slack_ids, mock_web_client
            )

            assert (
                invited_slack_ids == user_slack_ids
            )  # all users were invited successfully
            mock_invite_users.assert_called_once_with(
                user_slack_ids, mock_web_client
            )  # batch invite was called once
            mock_invite_individual.assert_called_once_with(
                user_slack_ids, mock_web_client
            )  # individual invite was called once


# XXX(dugab): Deduplicate tests
@pytest.mark.django_db
def test_invite_users(incident_channel: IncidentChannel, mock_web_client: WebClient):
    # Prepare test data
    incident_channel.channel_id = "test_channel"
    users: list[User] = UserFactory.create_batch(5)
    for user in users:
        user.slack_user = SlackUserFactory(user=user)

    # Mock the sub-methods of invite_users
    with (
        patch.object(
            incident_channel, "_get_active_slack_users", autospec=True
        ) as mock_get_active_users,
        patch.object(
            incident_channel, "_get_slack_id_list", autospec=True
        ) as mock_get_slack_ids,
        patch.object(
            incident_channel, "_invite_users_to_conversation", autospec=True
        ) as mock_invite,
    ):
        mock_get_active_users.return_value = users
        mock_get_slack_ids.return_value = {u.slack_user.slack_id for u in users}
        mock_invite.return_value = {u.slack_user.slack_id for u in users}

        # Call the method under test
        incident_channel.invite_users(users, client=mock_web_client)

        # Verify behavior
        mock_get_active_users.assert_called_once()
        mock_get_slack_ids.assert_called_once()
        mock_invite.assert_called_once_with(
            mock_get_slack_ids.return_value, client=mock_web_client
        )
        # Assert incident channel members are the same as the users
        assert set(incident_channel.incident.members.all()) == set(users)


@pytest.mark.django_db
def test_invite_users_one(
    incident_channel: IncidentChannel, user, slack_user, mock_web_client: WebClient
):
    mock_web_client.conversations_invite.return_value = {"ok": True}

    incident_channel.invite_users([user], client=mock_web_client)

    assert mock_web_client.conversations_invite.called
    assert slack_user.user in incident_channel.incident.members.all()


@pytest.mark.django_db
def test_invite_users_one_no_slack(
    incident_channel: IncidentChannel, mock_web_client: WebClient
):
    # Prepare test data
    incident_channel.channel_id = "test_channel"
    users: list[User] = UserFactory.create_batch(5)
    for user in users[:-1]:
        user.slack_user = SlackUserFactory(user=user)

    # Mock the sub-methods of invite_users
    with (
        patch.object(
            incident_channel, "_get_active_slack_users", autospec=True
        ) as mock_get_active_users,
        patch.object(
            incident_channel, "_get_slack_id_list", autospec=True
        ) as mock_get_slack_ids,
        patch.object(
            incident_channel, "_invite_users_to_conversation", autospec=True
        ) as mock_invite,
    ):
        mock_get_active_users.return_value = users[:-1]
        mock_get_slack_ids.return_value = {u.slack_user.slack_id for u in users[:-1]}
        mock_invite.return_value = {u.slack_user.slack_id for u in users[:-1]}

        # Call the method under test
        incident_channel.invite_users(users, client=mock_web_client)

        # Verify behavior
        mock_get_active_users.assert_called_once()
        mock_get_slack_ids.assert_called_once()
        mock_invite.assert_called_once_with(
            mock_get_slack_ids.return_value, client=mock_web_client
        )
        # Assert incident channel members are the same as the users, except the one without a slack user
        assert set(incident_channel.incident.members.all()) != set(users)
        # assert


@pytest.mark.django_db
def test_invite_users_all_inactive(
    incident_channel: IncidentChannel, caplog: pytest.LogCaptureFixture
):
    users = UserFactory.create_batch(5)
    for u in users:
        u.is_active = False

    # Mock the sub-methods of invite_users
    with (
        patch.object(
            incident_channel, "_get_slack_id_list", autospec=True
        ) as mock_get_slack_ids,
        caplog.at_level(logging.INFO),
    ):
        mock_get_slack_ids.return_value = {}

        incident_channel.invite_users(users, client=MagicMock())

        assert any(
            "No users to invite to the conversation" in x.message
            for x in caplog.records
        )


@pytest.mark.django_db
def test_channel_name_from_incident_no_argument(
    incident_channel: IncidentChannel, incident_saved: Incident
) -> None:
    incident_channel.incident = incident_saved
    expected_channel_name = channel_name_from_incident(incident_saved)
    assert incident_channel.channel_name_from_incident() == expected_channel_name


@pytest.mark.django_db
def test_channel_name_from_incident_argument_matches(
    incident_channel: IncidentChannel, incident_saved: Incident
):
    incident_channel.incident = incident_saved
    expected_channel_name = channel_name_from_incident(incident_saved)
    assert (
        incident_channel.channel_name_from_incident(incident_saved)
        == expected_channel_name
    )


@pytest.mark.django_db
def test_channel_name_from_incident_argument_does_not_match(
    incident_channel: IncidentChannel, incident_saved: Incident
):
    different_incident = IncidentFactory.create()
    incident_channel.incident = incident_saved
    with pytest.raises(
        ValueError,
        match=r"The incident passed as argument does not match the incident of the channel.",
    ) as exc_info:
        incident_channel.channel_name_from_incident(different_incident)
    assert (
        "The incident passed as argument does not match the incident of the channel."
        in str(exc_info.value)
    )


@pytest.mark.django_db
def test_rename_if_needed_no_rename(incident_channel: IncidentChannel):
    incident_channel.channel_name_from_incident = MagicMock()
    incident_channel.channel_name_from_incident.return_value = incident_channel.name
    incident_channel.save = MagicMock()
    incident_channel.rename_if_needed()
    incident_channel.save.assert_not_called()


@pytest.mark.django_db
def test_rename_if_needed_slack_api_error(
    incident_channel: IncidentChannel, mock_web_client: MockWebClient
):
    new_name = "new_name"
    incident_channel.channel_name_from_incident = MagicMock()
    incident_channel.channel_name_from_incident.return_value = new_name
    incident_channel.name = "old_name"
    mock_web_client.conversations_rename.side_effect = SlackApiError(
        "error", MagicMock(spec=SlackResponse)
    )
    incident_channel.save = MagicMock()

    assert incident_channel.rename_if_needed(client=mock_web_client) is None
    incident_channel.save.assert_not_called()


@pytest.mark.django_db
def test_rename_if_needed_success(
    incident_channel: IncidentChannel, mock_web_client: MockWebClient
):
    new_name = "new_name"
    incident_channel.channel_name_from_incident = lambda: new_name
    incident_channel.name = "old_name"
    mock_web_client.conversations_rename.return_value = {
        "ok": True,
        "channel": {
            "id": "new_id",
            "name": "new_name",
            "type": "new_type",
            "status": "new_status",
        },
    }
    incident_channel.save = MagicMock()

    assert incident_channel.rename_if_needed(client=mock_web_client) is True
    incident_channel.save.assert_called_once()


@pytest.mark.django_db
def test_rename_if_needed(incident_channel: IncidentChannel):
    mock_client = MagicMock(spec=WebClient)
    mock_client.conversations_rename.return_value = {
        "ok": True,
        "channel": {
            "id": "C123456",
            "name": "incident-renamed",
            "is_channel": True,
            "is_group": False,
            "is_im": False,
            "created": 1525285341,
            "is_archived": False,
            "is_general": False,
            "unlinked": 0,
            "creator": "U123456",
            "name_normalized": "incident-renamed",
            "is_shared": False,
            "is_ext_shared": False,
            "is_org_shared": False,
            "pending_shared": [],
            "is_pending_ext_shared": False,
            "is_member": True,
            "is_private": False,
            "is_mpim": False,
            "last_read": "1525285341.000100",
            "latest": {
                "user": "U123456",
                "type": "message",
                "text": "Hello",
                "ts": "1525285341.000100",
            },
            "unread_count": 0,
            "unread_count_display": 0,
            "members": [],
            "topic": {
                "value": "Incident channel",
                "creator": "U123456",
                "last_set": 1525285341,
            },
            "purpose": {
                "value": "Handle incidents",
                "creator": "U123456",
                "last_set": 1525285341,
            },
            "previous_names": [],
            "num_members": 1,
        },
    }

    result = incident_channel.rename_if_needed(client=mock_client)
    assert result is True
    assert incident_channel.name == "incident-renamed"


@pytest.mark.django_db
def test_set_incident_channel_topic(incident_channel: IncidentChannel) -> None:
    mock_client = MagicMock(spec=WebClient)
    mock_client.conversations_setTopic.return_value = {"ok": True}

    incident_channel.set_incident_channel_topic(client=mock_client)
    assert mock_client.conversations_setTopic.called


@pytest.mark.django_db
def test_archive_channel(incident_channel: IncidentChannel) -> None:
    mock_client = MagicMock(spec=WebClient)
    mock_client.conversations_archive.return_value = {"ok": True}

    result = incident_channel.archive_channel(client=mock_client)

    assert result is True
    assert incident_channel.status == ConversationStatus.ARCHIVED
    assert mock_client.conversations_archive.called


@pytest.mark.django_db
def test_rename_if_needed_error(incident_channel: IncidentChannel) -> None:
    mock_client = MagicMock(spec=WebClient)
    mock_client.conversations_rename.side_effect = SlackApiError(
        "Error renaming channel", {"ok": False}
    )

    result = incident_channel.rename_if_needed(client=mock_client)
    assert result is None
