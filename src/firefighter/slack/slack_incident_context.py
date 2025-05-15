from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from firefighter.firefighter.utils import get_first_in, get_in
from firefighter.incidents.models.incident import Incident
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.models.user import SlackUser

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)
INCIDENT_RESOLVING_STRATEGIES: list[IncidentResolveStrategy] = []

IncidentResolveStrategy = Callable[[dict[str, Any]], Literal[False] | Incident | None]


def incident_resolve_strategy(fn: IncidentResolveStrategy) -> IncidentResolveStrategy:
    INCIDENT_RESOLVING_STRATEGIES.append(fn)
    return fn


@incident_resolve_strategy
def get_incident_from_view_action(
    body: dict[str, Any],
) -> Literal[False] | Incident | None:
    """Get incident id from select incident in modal."""
    view_type = body.get("type")

    if view_type not in {"view_submission", "block_actions"}:
        return False
    actions = body.get("actions")
    if not isinstance(actions, list):
        return False
    action = get_first_in(
        actions, key="action_id", matches={"incident_update_select_incident"}
    )

    if not action:
        return False

    select_incident_value = get_in(action, "selected_option.value")
    logger.debug(action)
    logger.debug(select_incident_value)

    if not select_incident_value:
        return False
    try:
        incident_id = int(select_incident_value)
    except ValueError:
        logger.warning(
            f"Select incident ('{select_incident_value}') was not a valid incident ID!"
        )
        return None
    return Incident.objects.get(id=incident_id)


@incident_resolve_strategy
def get_incident_from_button_value(
    body: dict[str, Any],
) -> Incident | Literal[False] | None:
    """Try to get the incident ID from button value."""
    actions = body.get("actions")
    if not isinstance(actions, list):
        return False
    # XXX(dugab): this should not use an allow-list, but loop over values or use a specific prefix/suffix/pattern
    action = get_first_in(
        actions,
        key="action_id",
        matches={
            "open_modal_incident_update_roles",
            "open_modal_incident_update_status",
            "open_modal_downgrade_workflow",
        },
    )

    if not action:
        return False
    value = action.get("value")
    if not value:
        return False
    try:
        incident_id = int(value)
    except (ValueError, TypeError):
        logger.warning("Response.actions.action_id.value was not a valid incident ID!")
        return None
    return Incident.objects.get(id=incident_id)


@incident_resolve_strategy
def get_incident_from_view_submission_metadata(
    body: dict[str, Any],
) -> Incident | Literal[False] | None:
    """Get incident id from view modal metadata."""
    view_type = body.get("type")
    private_metadata = get_in(body, ["view", "private_metadata"])

    if not private_metadata:
        return False

    if view_type not in {"view_submission", "block_actions"}:
        return False

    try:
        incident_id = int(private_metadata)
    except ValueError:
        logger.warning(
            f"Response.view.private_metadata ('{private_metadata}') was not a valid incident ID!"
        )
        return None
    return Incident.objects.get(id=incident_id)


@incident_resolve_strategy
def get_incident_from_view_submission_selected(
    body: dict[str, Any],
) -> Incident | Literal[False] | None:
    """Get incident id from select incident in modal."""
    view_type = body.get("type")

    if view_type not in {"view_submission", "block_actions"}:
        return False

    select_incident_value = get_in(
        body,
        "view.state.values.incident_update_select_incident.incident_update_select_incident.selected_option.value",
    )
    if not select_incident_value:
        # Check the default value (appears selected to the user)
        select_incident_value = get_in(
            body,
            "view.state.values.incident_update_select_incident.incident_update_select_incident.initial_option.value",
        )
    if not select_incident_value:
        return False
    try:
        incident_id = int(select_incident_value)
    except ValueError:
        logger.warning(
            f"Select incident ('{select_incident_value}') was not a valid incident ID!"
        )
        return None
    return Incident.objects.get(id=incident_id)


@incident_resolve_strategy
def get_incident_from_body_channel_id_in_command(
    body: dict[str, Any],
) -> Incident | None:
    """Get an incident from a channel_id, found in commands."""
    channel_id = body.get("channel_id")
    if channel_id:
        channel = IncidentChannel.objects.filter(channel_id=channel_id).first()
        if channel and channel.incident:
            return channel.incident
    return None


@incident_resolve_strategy
def get_incident_from_body_channel_id_in_message_shortcut(
    body: dict[str, Any],
) -> Incident | None:
    """Get an incident from a channel.id, found in message shortcut."""
    channel_id = get_in(body, "channel.id")
    if channel_id:
        channel = IncidentChannel.objects.filter(channel_id=channel_id).first()
        if channel and channel.incident:
            return channel.incident
    return None


@incident_resolve_strategy
def get_incident_from_app_home_element(body: dict[str, Any]) -> Incident | None:
    """Get an incident from an action, found in app home accessory."""
    action = get_first_in(
        body.get("actions", []), "selected_option.value", ("update_status", "open_link")
    )
    if action is None:
        return None
    incident_id = action.get("block_id").strip(  # noqa: B005
        "app_home_incident_element_"
    )

    try:
        incident_id = int(incident_id)
    except ValueError:
        logger.warning(
            f"Select incident ('{incident_id}') was not a valid incident ID!"
        )
        return None
    return Incident.objects.get(id=incident_id)


@incident_resolve_strategy
def get_incident_from_reaction_event(body: dict[str, Any]) -> Incident | None:
    channel_id = get_in(body, "item.channel")
    if channel_id:
        channel = (
            IncidentChannel.objects.filter(channel_id=channel_id)
            .select_related("incident")
            .first()
        )
        if channel and channel.incident:
            return channel.incident
    return None


def get_incident_from_context(body: dict[str, Any]) -> Incident | None:
    """Returns an Incident or None, from a Slack body."""
    for strat in INCIDENT_RESOLVING_STRATEGIES:
        incident = strat(body)
        if incident:
            logger.debug(f"Found incident {incident.id} using {strat.__name__}")
            return incident

    logger.info(f"Incident could not be inferred from Slack body context: {body}")
    return None


def get_user_from_context(body: dict[str, Any]) -> User | None:
    """Returns a User or None, from a Slack body."""
    sender_id = get_in(body, "user.id", body.get("user_id"))

    return SlackUser.objects.get_user_by_slack_id(slack_id=sender_id)
