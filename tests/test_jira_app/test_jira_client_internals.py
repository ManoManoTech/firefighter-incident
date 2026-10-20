"""Tests for JiraClient workflow transitions, user resolution and assignment."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import Mock

import pytest
from django import db
from jira.exceptions import JIRAError

from firefighter.incidents.factories import UserFactory
from firefighter.incidents.models.user import User
from firefighter.jira_app.client import (
    JiraClient,
    JiraUserDatabaseError,
    JiraUserNotFoundError,
)
from firefighter.jira_app.models import JiraUser

INCOMING, IN_PROGRESS, CLOSED = 10, 20, 30


def _workflow_designer_layout() -> dict[str, Any]:
    """Raw workflow designer payload: Incoming -> In progress -> Closed, Closed -> Incoming.

    Ids use the designer encoding (``S<n>`` steps, ``I<n>`` initial transition) and
    camelCase keys, plus layout-only keys the client drops.
    """

    def status(step: int, status_id: int, name: str) -> dict[str, Any]:
        return {
            "id": f"S<{step}>",
            "name": name,
            "stepId": step,
            "statusId": status_id,
            "initial": step == 1,
            "x": 0,
            "y": 0,
        }

    def transition(
        name: str, source: str, target: str, *, initial: bool = False
    ) -> dict[str, Any]:
        return {
            "id": name,
            "name": name,
            "sourceId": source,
            "targetId": target,
            "actionId": 1,
            "initial": initial,
            "globalTransition": False,
            "loopedTransition": False,
            "transitionOptions": [],
            "sourceAngle": 0,
            "targetAngle": 0,
        }

    return {
        "layout": {
            "statuses": [
                status(1, INCOMING, "Incoming"),
                status(2, IN_PROGRESS, "In progress"),
                status(3, CLOSED, "Closed"),
            ],
            "transitions": [
                transition("Create", "I<1>", "S<1>", initial=True),
                transition("Start", "S<1>", "S<2>"),
                transition("Close", "S<2>", "S<3>"),
                transition("Reopen", "S<3>", "S<1>"),
            ],
        }
    }


@pytest.fixture
def workflow_jira_api(mock_jira_api: Mock) -> Mock:
    mock_jira_api.server_url = "https://jira.example"
    mock_jira_api._options = {"headers": {"X-Test": "1"}}
    mock_jira_api._session.get.return_value.json.return_value = (
        _workflow_designer_layout()
    )
    return mock_jira_api


def _issue_at(status_id: int) -> Mock:
    issue = Mock()
    issue.fields.status.id = str(status_id)
    return issue


class TestWorkflowBuilder:
    @staticmethod
    def test_parses_the_designer_payload(
        jira_client: JiraClient, workflow_jira_api: Mock
    ) -> None:
        workflow = jira_client._get_project_config_workflow_from_builder_base(
            "My workflow"
        )

        url = workflow_jira_api._session.get.call_args.args[0]
        assert url.startswith(
            "https://jira.example/rest/workflowDesigner/latest/workflows?name=My+workflow&"
        )
        assert [s["id"] for s in workflow["statuses"]] == [1, 2, 3]
        assert all("x" not in s and "y" not in s for s in workflow["statuses"])
        start = workflow["transitions"][1]
        assert (start["source_id"], start["target_id"]) == (1, 2)
        assert "source_angle" not in start
        assert "target_angle" not in start

    @staticmethod
    def test_global_transitions_and_shared_sources() -> None:
        def status(step: int, name: str) -> dict[str, Any]:
            return {"id": str(step), "name": name, "initial": False, "step_id": step}

        def transition(
            name: str, source: int, target: int, *, is_global: bool = False
        ) -> dict[str, Any]:
            return {
                "id": name,
                "name": name,
                "source_id": source,
                "target_id": target,
                "action_id": 1,
                "initial": False,
                "global_transition": is_global,
                "looped_transition": False,
                "transition_options": [],
            }

        infos = JiraClient._get_transitions(
            {
                "statuses": [status(1, "Open"), status(2, "Doing"), status(3, "Done")],
                "transitions": [
                    transition("Start", 1, 2),
                    transition("Skip", 1, 3),
                    transition("Abort", 2, 3, is_global=True),
                ],
            }
        )

        by_source = {info["status_id"]: info for info in infos}
        # Two transitions from Open are merged into one entry
        assert by_source[1]["target_statuses"] == {2, 3}
        # The global "Abort" is reachable from every status
        assert by_source[1]["transition_to_status"][3] == "Abort"
        assert by_source[2]["transition_to_status"][3] == "Abort"

    @staticmethod
    def test_transition_to_an_unknown_step_is_ignored(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def transition(name: str, source: int, target: int) -> dict[str, Any]:
            return {
                "id": name,
                "name": name,
                "source_id": source,
                "target_id": target,
                "action_id": 1,
                "initial": False,
                "global_transition": False,
                "looped_transition": False,
                "transition_options": [],
            }

        with caplog.at_level(logging.INFO, logger="firefighter.jira_app.client"):
            infos = JiraClient._get_transitions(
                {
                    "statuses": [
                        {"id": "1", "name": "Open", "initial": False, "step_id": 1},
                        {"id": "2", "name": "Done", "initial": False, "step_id": 2},
                    ],
                    "transitions": [
                        transition("Finish", 1, 2),
                        # Step 99 is not a status of the workflow
                        transition("Ghost", 1, 99),
                    ],
                }
            )

        by_source = {info["status_id"]: info for info in infos}
        assert by_source[1]["target_statuses"] == {2}
        assert "Ghost" not in by_source[1]["transition_to_status"].values()
        assert "Ignoring Transition Ghost: unknown step 1 or 99" in caplog.text


class TestTransitionIssueAuto:
    @staticmethod
    def test_applies_every_transition_on_the_path(
        jira_client: JiraClient, workflow_jira_api: Mock
    ) -> None:
        workflow_jira_api.issue.return_value = _issue_at(INCOMING)

        jira_client.transition_issue_auto(42, "Closed", "My workflow")

        applied = [
            c.kwargs["transition"]
            for c in workflow_jira_api.transition_issue.call_args_list
        ]
        assert applied == ["Start", "Close"]
        assert all(
            c.kwargs["issue"] == "42"
            for c in workflow_jira_api.transition_issue.call_args_list
        )

    @staticmethod
    def test_already_at_target_does_nothing(
        jira_client: JiraClient,
        workflow_jira_api: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        workflow_jira_api.issue.return_value = _issue_at(CLOSED)

        with caplog.at_level(logging.INFO):
            jira_client.transition_issue_auto(42, "Closed", "My workflow")

        workflow_jira_api.transition_issue.assert_not_called()
        assert "already at target status" in caplog.text

    @staticmethod
    def test_no_path_leaves_the_issue_unchanged(
        jira_client: JiraClient,
        workflow_jira_api: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        workflow_jira_api.issue.return_value = _issue_at(999)

        jira_client.transition_issue_auto(42, "Closed", "My workflow")

        workflow_jira_api.transition_issue.assert_not_called()
        assert "No transition path found" in caplog.text

    @staticmethod
    def test_unknown_target_status_does_nothing(
        jira_client: JiraClient,
        workflow_jira_api: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        jira_client.transition_issue_auto(42, "Archived", "My workflow")

        workflow_jira_api.issue.assert_not_called()
        assert "Could not find target status 'Archived'" in caplog.text

    @staticmethod
    def test_empty_workflow_is_logged(
        jira_client: JiraClient,
        workflow_jira_api: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        workflow_jira_api._session.get.return_value.json.return_value = {
            "layout": {"statuses": [], "transitions": []}
        }

        jira_client.transition_issue_auto(42, "Closed", "My workflow")

        assert "Could not find transitions for issue id=42" in caplog.text
        workflow_jira_api.transition_issue.assert_not_called()

    @staticmethod
    def test_failed_transition_stops_and_raises(
        jira_client: JiraClient, workflow_jira_api: Mock
    ) -> None:
        workflow_jira_api.issue.return_value = _issue_at(INCOMING)
        workflow_jira_api.transition_issue.side_effect = JIRAError("field required")

        with pytest.raises(JIRAError):
            jira_client.transition_issue_auto(42, "Closed", "My workflow")

        assert workflow_jira_api.transition_issue.call_count == 1


def test_get_issue_status_name(jira_client: JiraClient, mock_jira_api: Mock) -> None:
    mock_jira_api.issue.return_value.fields.status.name = "In progress"

    assert jira_client.get_issue_status_name(42) == "In progress"
    mock_jira_api.issue.assert_called_once_with("42", fields="status")


class TestFetchJiraUser:
    @staticmethod
    def test_empty_username_is_rejected(jira_client: JiraClient) -> None:
        with pytest.raises(ValueError, match="Invalid username"):
            jira_client._fetch_jira_user("")

    @staticmethod
    def test_unknown_user(jira_client: JiraClient, mock_jira_api: Mock) -> None:
        mock_jira_api.search_users.return_value = []

        with pytest.raises(JiraUserNotFoundError):
            jira_client._fetch_jira_user("ghost")

    @staticmethod
    def test_homonyms_are_told_apart_by_email(
        jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        other = Mock(raw={"emailAddress": "jdoe.other@example.com"})
        wanted = Mock(raw={"emailAddress": "jdoe@example.com"})
        mock_jira_api.search_users.return_value = [other, wanted]

        assert jira_client._fetch_jira_user("jdoe") is wanted

    @staticmethod
    def test_ambiguous_homonyms_are_rejected(
        jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        mock_jira_api.search_users.return_value = [
            Mock(raw={"emailAddress": "jdoe.a@example.com"}),
            Mock(raw={}),
        ]

        with pytest.raises(JiraUserNotFoundError, match="More than one"):
            jira_client._fetch_jira_user("jdoe")


@pytest.mark.django_db
class TestGetJiraUserFromJiraId:
    @staticmethod
    def _api_user(
        mock_jira_api: Mock, email: str | None, display_name: str | None = "Jane Doe"
    ) -> None:
        mock_jira_api.user.return_value = Mock(
            raw={"emailAddress": email, "displayName": display_name}
        )

    def test_existing_user_keeps_its_jira_user(
        self, jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        user = UserFactory.create(email="jane@example.com")
        existing = JiraUser.objects.create(id="old-account", user=user)
        self._api_user(mock_jira_api, "jane@example.com")

        assert jira_client.get_jira_user_from_jira_id("new-account") == existing

    def test_db_error_linking_an_existing_user(
        self, jira_client: JiraClient, mock_jira_api: Mock, mocker: Any
    ) -> None:
        UserFactory.create(email="jane@example.com")
        self._api_user(mock_jira_api, "jane@example.com")
        mocker.patch.object(JiraUser.objects, "create", side_effect=db.IntegrityError)

        with pytest.raises(JiraUserDatabaseError):
            jira_client.get_jira_user_from_jira_id("new-account")

    def test_db_error_linking_a_created_user(
        self, jira_client: JiraClient, mock_jira_api: Mock, mocker: Any
    ) -> None:
        self._api_user(mock_jira_api, "newcomer@example.com")
        mocker.patch.object(JiraUser.objects, "create", side_effect=db.IntegrityError)

        with pytest.raises(JiraUserDatabaseError):
            jira_client.get_jira_user_from_jira_id("new-account")
        assert User.objects.filter(email="newcomer@example.com").exists()

    def test_user_without_display_name_is_named_after_the_email(
        self, jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        self._api_user(mock_jira_api, "no.name@example.com", display_name=None)

        jira_user = jira_client.get_jira_user_from_jira_id("new-account")

        assert jira_user.user.name == "no.name"

    def test_db_error_creating_the_user(
        self, jira_client: JiraClient, mock_jira_api: Mock, mocker: Any
    ) -> None:
        self._api_user(mock_jira_api, "newcomer@example.com")
        mocker.patch.object(User.objects, "create", side_effect=db.IntegrityError)

        with pytest.raises(JiraUserDatabaseError):
            jira_client.get_jira_user_from_jira_id("new-account")

    def test_jira_api_error(self, jira_client: JiraClient, mock_jira_api: Mock) -> None:
        mock_jira_api.user.side_effect = JIRAError("boom")

        with pytest.raises(JiraUserNotFoundError):
            jira_client.get_jira_user_from_jira_id("new-account")

    def test_api_user_without_email(
        self, jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        self._api_user(mock_jira_api, None)

        with pytest.raises(JiraUserNotFoundError, match="no email address"):
            jira_client.get_jira_user_from_jira_id("new-account")


class TestAssignIssue:
    @staticmethod
    def test_success(jira_client: JiraClient, mock_jira_api: Mock) -> None:
        assert jira_client.assign_issue("INC-1", "acc-1") is True
        mock_jira_api.assign_issue.assert_called_once_with("INC-1", "acc-1")

    @staticmethod
    def test_failure_is_not_raised(
        jira_client: JiraClient, mock_jira_api: Mock
    ) -> None:
        mock_jira_api.assign_issue.side_effect = JIRAError(text="no permission")

        assert jira_client.assign_issue("INC-1", "acc-1") is False
