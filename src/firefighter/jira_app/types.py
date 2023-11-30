from __future__ import annotations

from typing import Any, NotRequired, TypedDict

_TransitionName = str
_StatusName = str
_StatusId = int
_TargetStatusId = int


class StatusTransitionInfo(TypedDict):
    status_id: _StatusId
    status_name: _StatusName
    target_statuses: set[_StatusId]
    transition_to_status: dict[_TargetStatusId, _TransitionName]


class Transition(TypedDict):
    id: str
    name: str
    source_id: int
    target_id: int
    action_id: int
    initial: bool
    global_transition: bool
    looped_transition: bool
    transition_options: list[Any]
    description: NotRequired[str]
    screen_name: NotRequired[str]


class Status(TypedDict):
    id: str
    name: str
    initial: bool
    step_id: int
    status_id: NotRequired[int]
    description: NotRequired[str]
    status_category: NotRequired[dict[str, Any]]


class WorkflowBuilderResponse(TypedDict):
    statuses: list[Status]
    transitions: list[Transition]
