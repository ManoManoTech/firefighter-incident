from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.dispatch import receiver
from django.utils import timezone
from slack_sdk.errors import SlackApiError

from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.incidents.signals import incident_updated
from firefighter.slack.messages.slack_messages import SlackMessageRoleAssignedToYou
from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from collections.abc import Iterable

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)
TZ = timezone.get_current_timezone()

ROLE_REMINDER_MIN_DAYS_INTERVAL: int = settings.FF_ROLE_REMINDER_MIN_DAYS_INTERVAL


@receiver(signal=incident_channel_done)
def incident_created_roles_dm(sender: Any, incident: Incident, **kwargs: Any) -> None:
    # Send the SlackMessageRoleAssignedToYou to all users with roles, at incident creation

    if ROLE_REMINDER_MIN_DAYS_INTERVAL == -1:
        return

    for role in incident.roles_set.all():
        message = SlackMessageRoleAssignedToYou(
            incident=incident, role_type=role.role_type, first_update=True
        )
        if role.user.slack_user and not has_user_had_the_same_role_recently(
            role.user, role_type=role.role_type
        ):
            logger.debug(
                f"Sending message to {role.user} for role {role.role_type.name}"
            )
            try:
                role.user.slack_user.send_private_message(message)
            except SlackApiError:
                logger.exception(
                    f"Failed to send message to {role.user.id} for role {role.role_type.name}"
                )


@receiver(signal=incident_updated, sender="update_roles")
def incident_updated_roles_dm(
    sender: Any,
    incident: Incident,
    incident_update: IncidentUpdate,
    updated_fields: list[str],
    **kwargs: Any,
) -> None:
    updated_roles = _get_updated_roles(incident, updated_fields)
    for role in updated_roles:
        message = SlackMessageRoleAssignedToYou(
            incident=incident, role_type=role.role_type, first_update=False
        )
        if role.user.slack_user and not has_user_had_the_same_role_recently(
            role.user, role_type=role.role_type
        ):
            try:
                role.user.slack_user.send_private_message(message)
            except SlackApiError:
                logger.exception(
                    f"Failed to send message to {role.user.id} for role {role.role_type.name}"
                )


def _get_updated_roles(
    incident: Incident, updated_fields: list[str]
) -> Iterable[IncidentRole]:
    if len(updated_fields) == 0:
        return []

    incident_roles: list[IncidentRole] = []
    # XXX Smelly
    for incident_role_type in IncidentRoleType.objects.all().filter(
        slug__in=[updated_field.removesuffix("_id") for updated_field in updated_fields]
    ):
        # Get the IncidentRole if it exists in DB, or create it locally with User=None
        try:
            incident_role = IncidentRole.objects.select_related(
                "user", "user__slack_user"
            ).get(incident=incident, role_type=incident_role_type)
            incident_roles.append(incident_role)
        except IncidentRole.DoesNotExist:
            pass

    return incident_roles


def has_user_had_the_same_role_recently(
    user: User, role_type: IncidentRoleType
) -> bool:
    recently_td = timedelta(days=ROLE_REMINDER_MIN_DAYS_INTERVAL)
    before_recent = datetime.datetime.now(tz=TZ) - recently_td
    return IncidentRole.objects.filter(
        user=user, role_type=role_type, updated_at__gte=before_recent
    ).exists()
