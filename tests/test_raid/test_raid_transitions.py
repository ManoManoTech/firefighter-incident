from __future__ import annotations

from firefighter.jira_app.client import JiraClient
from firefighter.jira_app.types import StatusTransitionInfo
from firefighter.jira_app.utils import (
    _states_to_transitions_names,
    _transition_path,
    get_status_id_from_name,
    get_transitions_to_apply,
)


def test__transition_path() -> None:
    statuses_transitions: dict[int, set[int]] = {1: {2, 3}, 2: {3}, 3: {4}, 4: set()}

    path = _transition_path(statuses_transitions, 1, 4)
    assert path == [1, 3, 4]

    path = _transition_path(statuses_transitions, 2, 4)
    assert path == [2, 3, 4]

    path = _transition_path(statuses_transitions, 3, 4)
    assert path == [3, 4]

    path = _transition_path(statuses_transitions, 1, 2)
    assert path == [1, 2]

    path = _transition_path(statuses_transitions, 4, 1)
    assert path == []


def test__states_to_transitions_names() -> None:
    statuses_transitions_names = {
        1: {2: "transition1", 3: "transition2"},
        2: {3: "transition3", 4: "transition4"},
        3: {4: "transition5"},
    }

    transitions = _states_to_transitions_names(statuses_transitions_names, [1, 2, 3, 4])
    assert transitions == ["transition1", "transition3", "transition5"]

    transitions = _states_to_transitions_names(statuses_transitions_names, [1, 3, 4])
    assert transitions == ["transition2", "transition5"]

    transitions = _states_to_transitions_names(statuses_transitions_names, [2, 3, 4])
    assert transitions == ["transition3", "transition5"]

    transitions = _states_to_transitions_names(statuses_transitions_names, [1, 2])
    assert transitions == ["transition1"]

    transitions = _states_to_transitions_names(statuses_transitions_names, [2, 4])
    assert transitions == ["transition4"]

    transitions = _states_to_transitions_names(statuses_transitions_names, [1])
    assert transitions == []


def test__get_transitions_to_apply() -> None:
    current_status_id = 1
    closed_state_id = 4
    transitions_info = [
        StatusTransitionInfo(
            status_id=1,
            status_name="Open",
            target_statuses={2, 3},
            transition_to_status={2: "Assign", 3: "Close"},
        ),
        StatusTransitionInfo(
            status_id=2,
            status_name="Assigned",
            target_statuses={3, 4},
            transition_to_status={3: "Reopen", 4: "Close"},
        ),
        StatusTransitionInfo(
            status_id=3,
            status_name="Closed",
            target_statuses={1},
            transition_to_status={1: "Reopen"},
        ),
        StatusTransitionInfo(
            status_id=4,
            status_name="Closed",
            target_statuses=set(),
            transition_to_status={},
        ),
    ]

    # Test if function returns correct transitions to close issue
    expected_transitions = ["Assign", "Close"]
    assert (
        get_transitions_to_apply(current_status_id, transitions_info, closed_state_id)
        == expected_transitions
    )

    # Test if function returns empty list if current_status_id is equal to closed_state_id
    current_status_id = 4
    assert (
        get_transitions_to_apply(current_status_id, transitions_info, closed_state_id)
        == []
    )

    # Test if function returns empty list if there's no path from current_status_id to closed_state_id
    current_status_id = 4
    closed_state_id = 1
    assert (
        get_transitions_to_apply(current_status_id, transitions_info, closed_state_id)
        == []
    )


def test__get_status_id_from_name() -> None:
    transitions_info = [
        StatusTransitionInfo(
            status_id=1,
            status_name="Open",
            target_statuses={2, 3},
            transition_to_status={2: "Assign", 3: "Close"},
        ),
        StatusTransitionInfo(
            status_id=2,
            status_name="Assigned",
            target_statuses={3, 4},
            transition_to_status={3: "Reopen", 4: "Close"},
        ),
        StatusTransitionInfo(
            status_id=3,
            status_name="Closed",
            target_statuses={1},
            transition_to_status={1: "Reopen"},
        ),
        StatusTransitionInfo(
            status_id=4,
            status_name="Resolved",
            target_statuses=set(),
            transition_to_status={},
        ),
    ]

    # Test if function returns correct status_id for a given status_name
    assert get_status_id_from_name(transitions_info, "Open") == 1
    assert get_status_id_from_name(transitions_info, "Assigned") == 2
    assert get_status_id_from_name(transitions_info, "Closed") == 3
    assert get_status_id_from_name(transitions_info, "Resolved") == 4

    # Test if function returns None for a non-existent status_name
    assert get_status_id_from_name(transitions_info, "NonExistent") is None


# --- GT-2184: path-finder must not detour through terminal statuses ---------

# Status ids mirroring the live "Incident workflow - v2023.03.13".
_INCOMING = 1
_IN_PROGRESS = 3
_CLOSED = 6
_CODE_REVIEW = 10300
_PENDING = 10873
_REPORTER_VALIDATION = 10874


def _incident_workflow_transitions() -> list[StatusTransitionInfo]:
    """Subset of the real incident workflow, with screened transitions INCLUDED
    (matching the post-fix `_get_transitions` behaviour). The only direct
    transitions into "Reporter validation" are screened ("Complete resolution",
    "Reject"); the only screen-free entry is "Cancel validation" from "Closed".
    """
    return [
        StatusTransitionInfo(
            status_id=_INCOMING,
            status_name="Incoming",
            target_statuses={_PENDING, _REPORTER_VALIDATION, _CODE_REVIEW},
            transition_to_status={
                _PENDING: "Route",
                _REPORTER_VALIDATION: "Reject",
                _CODE_REVIEW: "Code Review",
            },
        ),
        StatusTransitionInfo(
            status_id=_IN_PROGRESS,
            status_name="in progress",
            target_statuses={_PENDING, _REPORTER_VALIDATION, _CODE_REVIEW},
            transition_to_status={
                _PENDING: "Cancel resolution",
                _REPORTER_VALIDATION: "Complete resolution",
                _CODE_REVIEW: "Code Review",
            },
        ),
        StatusTransitionInfo(
            status_id=_CODE_REVIEW,
            status_name="Code Review",
            target_statuses={_IN_PROGRESS, _CLOSED, _REPORTER_VALIDATION},
            transition_to_status={
                _IN_PROGRESS: "Go back to resolution",
                _CLOSED: "Validate",
                _REPORTER_VALIDATION: "Complete resolution",
            },
        ),
        StatusTransitionInfo(
            status_id=_PENDING,
            status_name="Pending resolution",
            target_statuses={_INCOMING, _IN_PROGRESS, _REPORTER_VALIDATION},
            transition_to_status={
                _INCOMING: "Cancel routing",
                _IN_PROGRESS: "Start resolution",
                _REPORTER_VALIDATION: "Reject",
            },
        ),
        StatusTransitionInfo(
            status_id=_REPORTER_VALIDATION,
            status_name="Reporter validation",
            target_statuses={_CLOSED, _IN_PROGRESS, _INCOMING},
            transition_to_status={
                _CLOSED: "Validate",
                _IN_PROGRESS: "Go back to resolution",
                _INCOMING: "Go back to incoming",
            },
        ),
        StatusTransitionInfo(
            status_id=_CLOSED,
            status_name="Closed",
            target_statuses={_REPORTER_VALIDATION, _PENDING},
            transition_to_status={
                _REPORTER_VALIDATION: "Cancel validation",
                _PENDING: "Reopen",
            },
        ),
    ]


def test__transition_path_does_not_traverse_blocked_intermediate() -> None:
    # 1 -> 2 -> 3, where 2 is terminal. Blocking 2 as an intermediate makes 3
    # unreachable, instead of detouring through it.
    graph: dict[int, set[int]] = {1: {2}, 2: {3}, 3: set()}

    assert _transition_path(graph, 1, 3) == [1, 2, 3]
    assert _transition_path(graph, 1, 3, blocked_states={2}) == []
    # The target itself may be a blocked status (e.g. closing an issue).
    assert _transition_path(graph, 1, 2, blocked_states={2}) == [1, 2]
    # Leaving a blocked start status is allowed.
    assert _transition_path(graph, 2, 3, blocked_states={2}) == [2, 3]


def test_path_to_reporter_validation_is_direct_and_skips_closed() -> None:
    info = _incident_workflow_transitions()
    reporter_validation = get_status_id_from_name(info, "Reporter validation")
    assert reporter_validation is not None

    transitions = get_transitions_to_apply(_IN_PROGRESS, info, reporter_validation)

    # Direct one-hop transition via the (screened-but-usable) "Complete resolution",
    # never routing through "Closed".
    assert transitions == ["Complete resolution"]


def test_path_to_reporter_validation_never_routes_through_closed() -> None:
    # Simulate a workflow where the only entry into "Reporter validation" is via
    # "Closed" (Cancel validation). The terminal guard must refuse the detour and
    # return no path, rather than transiently closing the ticket.
    info = _incident_workflow_transitions()
    for transition_info in info:
        if transition_info["status_name"] != "Closed":
            transition_info["target_statuses"].discard(_REPORTER_VALIDATION)
            transition_info["transition_to_status"].pop(_REPORTER_VALIDATION, None)

    reporter_validation = get_status_id_from_name(info, "Reporter validation")
    assert reporter_validation is not None

    transitions = get_transitions_to_apply(_IN_PROGRESS, info, reporter_validation)

    assert transitions == []


def test_closing_still_reaches_closed_when_it_is_the_target() -> None:
    info = _incident_workflow_transitions()
    closed = get_status_id_from_name(info, "Closed")
    assert closed is not None

    transitions = get_transitions_to_apply(_IN_PROGRESS, info, closed)

    # "Closed" is the explicit target, so it is reachable despite being terminal.
    # The final hop into "Closed" is the "Validate" transition.
    assert transitions
    assert transitions[-1] == "Validate"


def test__get_transitions_keeps_screened_transitions() -> None:
    # Regression for GT-2184: a transition with a screen must NOT be dropped from
    # the graph. It is usable over the API as long as its screen has no required
    # field (FF submits an empty field set). Before the fix, _get_transitions
    # discarded every screened transition, leaving "Reporter validation"
    # reachable only via "Closed".
    workflow = {
        "statuses": [
            {
                "step_id": _IN_PROGRESS,
                "status_id": _IN_PROGRESS,
                "name": "in progress",
                "initial": False,
            },
            {
                "step_id": _REPORTER_VALIDATION,
                "status_id": _REPORTER_VALIDATION,
                "name": "Reporter validation",
                "initial": False,
            },
        ],
        "transitions": [
            {
                "source_id": _IN_PROGRESS,
                "target_id": _REPORTER_VALIDATION,
                "name": "Complete resolution",
                "initial": False,
                "global_transition": False,
                "screen_name": "IM: Resolution screen",
            },
        ],
    }

    transitions_info = JiraClient._get_transitions(workflow)  # type: ignore[arg-type]

    in_progress = next(
        t for t in transitions_info if t["status_id"] == _IN_PROGRESS
    )
    assert _REPORTER_VALIDATION in in_progress["target_statuses"]
    assert (
        in_progress["transition_to_status"][_REPORTER_VALIDATION]
        == "Complete resolution"
    )


def test__get_transitions_still_drops_initial_transitions() -> None:
    # The "initial" transition (issue creation) must still be excluded — only the
    # screen filter was relaxed.
    workflow = {
        "statuses": [
            {
                "step_id": _IN_PROGRESS,
                "status_id": _IN_PROGRESS,
                "name": "in progress",
                "initial": False,
            },
            {
                "step_id": _REPORTER_VALIDATION,
                "status_id": _REPORTER_VALIDATION,
                "name": "Reporter validation",
                "initial": False,
            },
        ],
        "transitions": [
            {
                "source_id": _IN_PROGRESS,
                "target_id": _REPORTER_VALIDATION,
                "name": "Create",
                "initial": True,
                "global_transition": False,
            },
        ],
    }

    transitions_info = JiraClient._get_transitions(workflow)  # type: ignore[arg-type]

    assert transitions_info == []
