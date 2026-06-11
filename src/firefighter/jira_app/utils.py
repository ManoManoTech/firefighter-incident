from __future__ import annotations

import logging
import re
from functools import cache
from typing import TYPE_CHECKING, Final, TypeVar

if TYPE_CHECKING:
    from firefighter.jira_app.types import (
        StatusTransitionInfo,
        _StatusId,
        _StatusName,
        _TargetStatusId,
        _TransitionName,
    )

_SNAKE_CASE_PATTERN: Final[re.Pattern[str]] = re.compile(r"(.)([A-Z]+)")

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Terminal statuses that must never be used as an *intermediate* hop when
# computing a transition path. They remain valid as an explicit target (e.g.
# closing an incident), but the path-finder must not route *through* them to
# reach a non-terminal status. Without this guard, the only screen-free way to
# reach "Reporter validation" in the incident workflow is via "Closed", which
# transiently marks the ticket as Done on mitigation (see GT-2184).
TERMINAL_STATUS_NAMES: Final[frozenset[str]] = frozenset({"Closed"})


def _transition_path[T](
    statuses_transitions: dict[T, set[T]],
    from_state: T,
    to_state: T,
    blocked_states: set[T] | None = None,
) -> list[T]:
    """Returns the path to transition from one status to another.
        Includes the from_state and to_state.

        If the path is not found, returns an empty list.

    Args:
        statuses_transitions (dict[T, set[T]]): dict of statuses and their targets
        from_state (T): starting status
        to_state (T): ending status
        blocked_states (set[T] | None): statuses that must not be used as
            intermediate hops. The from_state and to_state are never blocked, so
            leaving a blocked status or targeting it directly still works.

    Returns:
        list[T]: list of statuses to transition from from_state to to_state
    """
    if from_state == to_state:
        return []
    blocked = set(blocked_states or ())
    blocked.discard(from_state)
    blocked.discard(to_state)
    visited = set()
    queue = [[from_state]]
    while queue:
        path = queue.pop(0)
        node = path[-1]
        if node not in visited:
            visited.add(node)
            for adjacent in statuses_transitions.get(node, []):
                if adjacent in blocked:
                    continue
                new_path = list(path)
                new_path.append(adjacent)
                queue.append(new_path)
                if adjacent == to_state:
                    return new_path
    logger.warning(f"No path found for from_state {from_state} to to_state {to_state}")
    return []


def _states_to_transitions_names(
    statuses_transitions_names: dict[_StatusId, dict[_StatusId, _StatusName]],
    states: list[_StatusId],
) -> list[_StatusName]:
    return [
        statuses_transitions_names[states[i]][states[i + 1]]
        for i in range(len(states) - 1)
    ]


def get_transitions_to_apply(
    current_status_id: _StatusId,
    transitions_info: list[StatusTransitionInfo],
    closed_state_id: _StatusId,
    terminal_status_names: frozenset[str] = TERMINAL_STATUS_NAMES,
) -> list[_StatusName]:
    # Get path to target state
    statuses_targets: dict[_StatusId, set[_TargetStatusId]] = {
        k["status_id"]: k["target_statuses"] for k in transitions_info
    }
    # Identify terminal statuses (e.g. "Closed") by name so the path-finder never
    # routes *through* them to reach a non-terminal target. The target itself is
    # exempt (handled in _transition_path), so closing an issue still works.
    blocked_states: set[_StatusId] = {
        k["status_id"]
        for k in transitions_info
        if k["status_name"] in terminal_status_names
    }
    path_states = _transition_path(
        statuses_targets,
        current_status_id,
        closed_state_id,
        blocked_states=blocked_states,
    )

    # Get transitions to apply from path
    statuses_transitions_names: dict[
        _StatusId, dict[_TargetStatusId, _TransitionName]
    ] = {k["status_id"]: k["transition_to_status"] for k in transitions_info}
    return _states_to_transitions_names(statuses_transitions_names, path_states)


def get_status_id_from_name(
    transitions_info: list[StatusTransitionInfo], status_name: str
) -> _StatusId | None:
    return next(
        (k["status_id"] for k in transitions_info if k["status_name"] == status_name),
        None,
    )


@cache
def _snake_case_key(key: str) -> str:
    s1 = _SNAKE_CASE_PATTERN.sub(r"\1_\2", key)
    return s1.lower()


def pythonic_keys[T](d: T) -> T:
    """Converts camelCase keys in a dict or list of dict to snake_case. Works recursively."""
    if isinstance(d, dict):
        new_d = {}
        for key, value in d.items():
            new_key = _snake_case_key(key)
            new_d[new_key] = pythonic_keys(value)
        return new_d  # type: ignore[return-value]
    if isinstance(d, list):
        return [pythonic_keys(v) for v in d]  # type: ignore[return-value]
    return d
