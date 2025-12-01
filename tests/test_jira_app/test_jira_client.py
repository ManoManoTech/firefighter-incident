from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from django import db
from jira import exceptions

from firefighter.incidents.factories import UserFactory
from firefighter.jira_app.client import (
    JiraAPIError,
    JiraClient,
    JiraUserDatabaseError,
    JiraUserNotFoundError,
)
from firefighter.jira_app.models import JiraUser


def _make_client() -> JiraClient:
    client = JiraClient()
    client.__dict__.pop("jira", None)
    return client


def _stub_jira(**methods: Any) -> SimpleNamespace:
    return SimpleNamespace(**methods)


class DummyIssue(SimpleNamespace):
    key: str
    id: str


def test_fetch_jira_user_validates_username() -> None:
    client = _make_client()
    with pytest.raises(ValueError):
        client._fetch_jira_user("")


def test_fetch_jira_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    stub = _stub_jira(search_users=lambda query: [])
    client.__dict__["jira"] = stub
    with pytest.raises(JiraUserNotFoundError):
        client._fetch_jira_user("unknown")


def test_fetch_jira_user_picks_matching_email(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    users = [
        SimpleNamespace(raw={"emailAddress": "someone@example.com"}),
        SimpleNamespace(raw={"emailAddress": "john@example.com"}),
    ]
    stub = _stub_jira(search_users=lambda query: users)
    client.__dict__["jira"] = stub
    result = client._fetch_jira_user("john")
    assert result is users[1]


def test_fetch_jira_user_multiple_without_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client()
    users = [
        SimpleNamespace(raw={"emailAddress": "other@example.com"}),
        SimpleNamespace(raw={"emailAddress": "none@example.com"}),
    ]
    stub = _stub_jira(search_users=lambda query: users)
    client.__dict__["jira"] = stub
    with pytest.raises(JiraUserNotFoundError):
        client._fetch_jira_user("john")


@pytest.mark.django_db
def test_get_jira_user_from_user_returns_cached() -> None:
    user = UserFactory()
    jira_user = JiraUser.objects.create(id="acct-1", user=user)
    client = _make_client()
    assert client.get_jira_user_from_user(user) == jira_user


@pytest.mark.django_db
def test_get_jira_user_from_user_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    user = UserFactory(email="fetch@example.com")
    jira_user_obj = SimpleNamespace(raw={"accountId": "acct-2"})
    client = _make_client()
    monkeypatch.setattr(client, "_fetch_jira_user", lambda username: jira_user_obj)
    result = client.get_jira_user_from_user(user)
    assert result.id == "acct-2"
    assert result.user == user


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    user = UserFactory()
    recorded = JiraUser.objects.create(id="acct-3", user=user)
    client = _make_client()
    monkeypatch.setattr(
        client, "_get_user_from_api", lambda account_id: (_stub_jira(), user.email)
    )
    assert client.get_jira_user_from_jira_id("acct-3") == recorded


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_links_existing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = UserFactory(email="link@example.com")
    jira_api_user = _stub_jira(raw={"displayName": "Link User"})
    client = _make_client()
    monkeypatch.setattr(
        client,
        "_get_user_from_api",
        lambda account_id: (jira_api_user, "link@example.com"),
    )
    result = client.get_jira_user_from_jira_id("acct-4")
    assert result.user == user
    assert result.id == "acct-4"


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_creates_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jira_api_user = _stub_jira(raw={"displayName": "New User"})
    created_user = UserFactory()
    client = _make_client()
    monkeypatch.setattr(
        client,
        "_get_user_from_api",
        lambda account_id: (jira_api_user, created_user.email),
    )
    monkeypatch.setattr(
        client,
        "_create_user_from_jira_info",
        lambda _id, _api_user, _email, _username: created_user,
    )
    result = client.get_jira_user_from_jira_id("acct-5")
    assert result.user == created_user


def test_get_jira_user_from_jira_id_invalid() -> None:
    client = _make_client()
    with pytest.raises(ValueError):
        client.get_jira_user_from_jira_id("")


def test_get_watchers_handles_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()

    def watchers(_: Any) -> None:
        raise exceptions.JIRAError(status_code=404, text="not found")

    client.__dict__["jira"] = _stub_jira(watchers=watchers)
    assert client.get_watchers_from_jira_ticket("INC-1") == []


def test_get_watchers_returns_list(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    watcher_payload = SimpleNamespace(raw={"watchers": ["user"]})
    client.__dict__["jira"] = _stub_jira(watchers=lambda issue: watcher_payload)
    assert client.get_watchers_from_jira_ticket("INC-2") == ["user"]


def test_get_user_from_api_requires_email(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    jira_user = _stub_jira(raw={"emailAddress": None})
    client.__dict__["jira"] = _stub_jira(user=lambda account_id: jira_user)
    with pytest.raises(JiraUserNotFoundError):
        client._get_user_from_api("acct-6")


def test_get_transitions_filters_and_combines() -> None:
    workflow = {
        "statuses": [
            {"step_id": 1, "status_id": 10, "name": "Open"},
            {"step_id": 2, "status_id": 20, "name": "Closed"},
        ],
        "transitions": [
            {
                "name": "Start",
                "source_id": 1,
                "target_id": 2,
                "initial": False,
                "global_transition": False,
            },
            {
                "name": "Init",
                "source_id": 1,
                "target_id": 2,
                "screen_name": "Screen",
                "initial": False,
                "global_transition": False,
            },
            {
                "name": "GlobalClose",
                "source_id": 1,
                "target_id": 2,
                "initial": False,
                "global_transition": True,
            },
        ],
    }
    client = _make_client()
    info = client._get_transitions(workflow)
    assert len(info) == 1
    entry = info[0]
    assert entry["status_id"] == 10
    assert entry["transition_to_status"][20] == "GlobalClose"


def test_create_postmortem_issue_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    created_issue = DummyIssue(key="INC-1", id="1000")

    def create_issue(fields: Any) -> DummyIssue:
        return created_issue

    link_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        client,
        "_create_issue_link_safe",
        lambda parent_issue_key, postmortem_issue_key: link_calls.append((
            parent_issue_key,
            postmortem_issue_key,
        )),
    )
    client.__dict__["jira"] = _stub_jira(create_issue=create_issue)
    result = client.create_postmortem_issue(
        project_key="INC",
        issue_type="Postmortem",
        fields={"summary": "Test"},
        parent_issue_key="INC-0",
    )
    assert result == {"key": "INC-1", "id": "1000"}
    assert link_calls == [("INC-0", "INC-1")]


def test_create_postmortem_issue_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()

    def create_issue(fields: Any) -> None:
        raise exceptions.JIRAError(status_code=500, text="boom")

    client.__dict__["jira"] = _stub_jira(create_issue=create_issue)
    with pytest.raises(JiraAPIError):
        client.create_postmortem_issue("INC", "Postmortem", {"summary": "bad"})


def test_create_issue_link_safe_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    issue_calls: list[str] = []
    created_links: list[tuple[str, str, str]] = []

    def issue(key: str) -> None:
        issue_calls.append(key)

    def create_issue_link(
        type: str, inwardIssue: str, outwardIssue: str, comment: dict[str, str]
    ) -> None:
        created_links.append((type, inwardIssue, outwardIssue))

    client.__dict__["jira"] = _stub_jira(
        issue=issue, create_issue_link=create_issue_link
    )
    client._create_issue_link_safe("INC-1", "POST-1")
    assert created_links[0][0] == "Relates"


def test_create_issue_link_safe_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client()

    def issue(_: str) -> None:
        raise exceptions.JIRAError(status_code=404, text="missing")

    client.__dict__["jira"] = _stub_jira(issue=issue)
    client._create_issue_link_safe("INC-1", "POST-1")


def test_assign_issue_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    client.__dict__["jira"] = _stub_jira(
        assign_issue=lambda issue_key, account_id: None
    )
    assert client.assign_issue("INC-1", "acct") is True

    def failing_assign(issue_key: str, account_id: str) -> None:
        raise exceptions.JIRAError(status_code=400, text="fail")

    client.__dict__["jira"] = _stub_jira(assign_issue=failing_assign)
    assert client.assign_issue("INC-1", "acct") is False


def test_transition_issue_auto_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    workflow = {"statuses": [], "transitions": []}
    monkeypatch.setattr(
        client,
        "_get_project_config_workflow_from_builder_base",
        lambda workflow_name: workflow,
    )
    transitions_info = [
        {
            "status_id": 1,
            "status_name": "Open",
            "target_statuses": {2},
            "transition_to_status": {2: "Close"},
        }
    ]
    monkeypatch.setattr(client, "_get_transitions", lambda response: transitions_info)
    monkeypatch.setattr(
        "firefighter.jira_app.client.get_status_id_from_name",
        lambda info, status_name: 2,
    )
    monkeypatch.setattr(
        "firefighter.jira_app.client.get_transitions_to_apply",
        lambda current, info, target: ["Close"],
    )
    recorded: list[str] = []
    issue = SimpleNamespace(fields=SimpleNamespace(status=SimpleNamespace(id="1")))
    client.__dict__["jira"] = _stub_jira(
        issue=lambda issue_id: issue,
        transition_issue=lambda **kwargs: recorded.append(kwargs["transition"]),
    )
    client.transition_issue_auto("INC-1", "Closed", "WF")
    assert recorded == ["Close"]


def test_transition_issue_auto_handles_missing_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client()
    monkeypatch.setattr(
        client,
        "_get_project_config_workflow_from_builder_base",
        lambda workflow_name: {"statuses": [], "transitions": []},
    )
    monkeypatch.setattr(client, "_get_transitions", lambda response: [1])
    monkeypatch.setattr(
        "firefighter.jira_app.client.get_status_id_from_name",
        lambda info, status_name: None,
    )
    client.__dict__["jira"] = _stub_jira(issue=lambda issue_id: None)
    client.transition_issue_auto("INC-1", "Closed", "WF")


def test_transition_issue_auto_no_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    monkeypatch.setattr(
        client,
        "_get_project_config_workflow_from_builder_base",
        lambda workflow_name: {"statuses": [], "transitions": []},
    )
    monkeypatch.setattr(client, "_get_transitions", lambda _: [])
    client.transition_issue_auto("INC-1", "Closed", "WF")


def test_project_config_workflow_from_builder_base_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "layout": {
            "statuses": [
                {
                    "id": "S<1>",
                    "step_id": 1,
                    "status_id": "S<10>",
                    "name": "Open",
                    "x": 1,
                    "y": 2,
                },
            ],
            "transitions": [
                {
                    "name": "Close",
                    "source_id": "S<1>",
                    "target_id": "S<2>",
                    "initial": False,
                    "global_transition": False,
                }
            ],
        }
    }
    session = SimpleNamespace(
        get=lambda url, headers: SimpleNamespace(json=lambda: payload)
    )
    client = _make_client()
    client.__dict__["jira"] = SimpleNamespace(
        server_url="https://example", _session=session, _options={"headers": {"X": "Y"}}
    )
    result = client._get_project_config_workflow_from_builder_base("WF")
    assert result["statuses"][0]["id"] == 1
    assert result["transitions"][0]["source_id"] == 1


def test_project_config_workflow_base(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"ok": True}
    session = SimpleNamespace(
        get=lambda url, headers: SimpleNamespace(json=lambda: payload)
    )
    client = _make_client()
    client.__dict__["jira"] = SimpleNamespace(
        server_url="https://example", _session=session, _options={"headers": {"X": "Y"}}
    )
    assert client._get_project_config_workflow_base("INC", "WF") == payload


@pytest.mark.django_db
def test_create_user_from_jira_info_handles_db_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client()

    def failing_create(*args: Any, **kwargs: Any) -> None:
        raise db.IntegrityError()

    monkeypatch.setattr(
        "firefighter.jira_app.client.User.objects.create",
        failing_create,
    )
    with pytest.raises(JiraUserDatabaseError):
        client._create_user_from_jira_info(
            "acct", _stub_jira(raw={"displayName": "X"}), "x@example.com", "x"
        )


@pytest.mark.django_db
def test_get_jira_user_from_jira_id_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client()
    jira_api_user = _stub_jira(raw={"displayName": "User"})
    monkeypatch.setattr(
        client,
        "_get_user_from_api",
        lambda account_id: (jira_api_user, "db@example.com"),
    )
    monkeypatch.setattr(
        "firefighter.jira_app.client.User.objects.get",
        lambda **kwargs: UserFactory(email="db@example.com"),
    )

    def failing_create(*args: Any, **kwargs: Any) -> None:
        raise db.IntegrityError()

    monkeypatch.setattr(
        "firefighter.jira_app.client.JiraUser.objects.create",
        failing_create,
    )
    with pytest.raises(JiraUserDatabaseError):
        client.get_jira_user_from_jira_id("acct-err")
