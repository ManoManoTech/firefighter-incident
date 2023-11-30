from __future__ import annotations

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
