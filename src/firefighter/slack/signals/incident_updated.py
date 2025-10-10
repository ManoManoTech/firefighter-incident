from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.dispatch.dispatcher import receiver

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.signals import incident_key_events_updated, incident_updated
from firefighter.slack.messages.slack_messages import (
    SlackMessageDeployWarning,
    SlackMessageIncidentDowngradeHint,
    SlackMessageIncidentRolesUpdated,
    SlackMessageIncidentStatusUpdated,
)
from firefighter.slack.models.conversation import Conversation, ConversationType
from firefighter.slack.rules import (
    should_publish_in_general_channel,
    should_publish_in_it_deploy_channel,
)

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import ManyRelatedManager

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate
    from firefighter.incidents.models.priority import Priority
    from firefighter.incidents.models.user import User
logger = logging.getLogger(__name__)
# pylint: disable=unused-argument


@receiver(signal=incident_updated, sender="update_status")
def incident_updated_update_status_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    # Update Slack channel if needed
    incident.conversation.rename_if_needed()

    # Update topic if needed
    if (
        "priority_id" in updated_fields
        or "incident_category_id" in updated_fields
        or "_status" in updated_fields
    ):
        incident.conversation.set_incident_channel_topic()

    publish_status_update(
        incident=incident,
        incident_update=incident_update,
        status_changed=bool("_status" in updated_fields),
        old_priority=kwargs.get("old_priority"),
    )


@receiver(signal=incident_updated, sender="update_status")
def incident_updated_check_dowmgrade_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    if not incident_update.priority or incident_update.priority.value <= 2:
        return

    try:
        commander_role = (
            incident.roles_set.filter(role_type__slug="commander")
            .select_related("user__slack_user")
            .get()
        )
        slack_user = commander_role.user.slack_user
    except incident.roles_set.model.DoesNotExist:
        slack_user = None

    if slack_user is None:
        if (
            incident_update.created_by is None
            or not hasattr(incident_update.created_by, "slack_user")
            or incident_update.created_by.slack_user is None
        ):
            return
        slack_user = incident_update.created_by.slack_user

    incident.conversation.send_message_ephemeral(
        message=SlackMessageIncidentDowngradeHint(
            incident=incident, incident_update=incident_update
        ),
        user=slack_user,
    )


@receiver(signal=incident_updated, sender="update_roles")
def incident_updated_update_roles_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    # Publish a message to the conversation
    update_roles_message = SlackMessageIncidentRolesUpdated(
        incident=incident,
        incident_update=incident_update,
        first_update=False,
        updated_fields=updated_fields,
    )
    incident.conversation.send_message_and_save(update_roles_message)

    # Check if updated_fields map to existing IncidentRoleTypes that have a IncidentRole for this incident
    # If so, invite the users
    users_with_roles = incident.roles_set.filter(
        role_type__slug__in=[
            updated_field.removesuffix("_id") for updated_field in updated_fields
        ]
    ).select_related("user", "user__slack_user")
    users_to_invite = [
        role.user for role in users_with_roles if role.user.slack_user is not None
    ]

    incident.conversation.invite_users(list(users_to_invite))


@receiver(signal=incident_updated)
# pylint: disable=unused-argument
def incident_updated_reinvite_handler(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    if incident.conversation.type == ConversationType.PRIVATE_CHANNEL:
        return

    # Rebuild the invite list
    full_invite_list: set[User] = set(incident.build_invite_list())

    # Check if users from the invite list are not in the channel
    members_manager: ManyRelatedManager[User] = incident.conversation.members  # type: ignore [assignment]
    already_invited_users = members_manager.all()
    missing_users = full_invite_list.difference(already_invited_users)

    if len(missing_users) > 0:
        incident.conversation.invite_users(list(missing_users))
    else:
        logger.info(f"No users to re-invite for incident {incident.id}")


@receiver(signal=incident_key_events_updated)
def incident_key_events_updated_handler(
    sender: Any,
    incident: Incident,
    **kwargs: Any,
) -> None:
    logger.info("Received incident_key_events_updated signal")
    # Skip key events for incidents closed directly
    if incident.closure_reason:
        logger.info(f"Skipping key events update for incident {incident.id} (direct closure)")
        return

    # Everything in Slack views trigger the Slack handshake, so we delay the import
    from firefighter.slack.views.modals.key_event_message import (  # noqa: PLC0415
        SlackMessageKeyEvents,
    )

    incident.conversation.send_message_and_save(SlackMessageKeyEvents(incident))


def publish_status_update(
    incident: Incident,
    incident_update: IncidentUpdate,
    *,
    status_changed: bool = False,
    old_priority: Priority | None = None,
) -> None:
    """Publishes an update to the incident status."""
    message = SlackMessageIncidentStatusUpdated(
        incident=incident,
        incident_update=incident_update,
        in_channel=True,
    )
    incident.conversation.send_message_and_save(message)

    # Post to #tech-incidents
    if should_publish_in_general_channel(
        incident=incident, incident_update=incident_update, old_priority=old_priority
    ):
        publish_update_in_general_channel(
            incident=incident,
            incident_update=incident_update,
            status_changed=status_changed,
            old_priority=old_priority,
        )

    if (
        incident.ask_for_milestones
        and status_changed
        and incident.status >= IncidentStatus.MITIGATED
        and not incident.closure_reason  # Don't show key events for direct closures
    ):
        from firefighter.slack.views.modals.key_event_message import (  # noqa: PLC0415
            SlackMessageKeyEvents,
        )

        incident.conversation.send_message_and_save(
            SlackMessageKeyEvents(incident=incident)
        )

    if should_publish_in_it_deploy_channel(incident=incident):
        announcement_it_deploy = SlackMessageDeployWarning(incident)
        announcement_it_deploy.id = f"{announcement_it_deploy.id}_{incident.id}"

        it_deploy_conversation = Conversation.objects.get_or_none(tag="it_deploy")
        if it_deploy_conversation:
            it_deploy_conversation.send_message_and_save(announcement_it_deploy)
        else:
            logger.warning(
                "Could not find it_deploy conversation! Is there a channel with tag it_deploy?"
            )


def publish_update_in_general_channel(
    incident: Incident,
    incident_update: IncidentUpdate,
    *,
    status_changed: bool = False,
    old_priority: Priority | None = None,
) -> None:
    update_status_message_global = SlackMessageIncidentStatusUpdated(
        incident_update=incident_update,
        incident=incident,
        in_channel=False,
        status_changed=status_changed,
        old_priority=old_priority,
    )
    tech_incidents_conversation = Conversation.objects.get_or_none(tag="tech_incidents")
    if tech_incidents_conversation:
        tech_incidents_conversation.send_message_and_save(update_status_message_global)
    else:
        logger.warning(
            "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
        )
