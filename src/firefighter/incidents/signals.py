from __future__ import annotations

from typing import TYPE_CHECKING

import django.dispatch

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident  # noqa: F401
    from firefighter.incidents.models.incident_update import (  # noqa: F401
        IncidentUpdate,
    )
    from firefighter.incidents.models.priority import Priority  # noqa: F401
    from firefighter.incidents.models.user import User  # noqa: F401

incident_created = django.dispatch.Signal()
"""Signal sent when an incident is created

Args:
    incident (Incident): The incident that was created
"""


incident_closed = django.dispatch.Signal()
"""Signal sent when an incident is closed

Args:
    sender (Any): The sender of the signal __name__
    incident (Incident): The incident that was closed
"""


incident_updated = django.dispatch.Signal()
"""Signal sent when an incident is updated.

Args:
    sender (str | Any): The sender of the signal __name__
    incident (Incident): The incident that was updated
    incident_update (IncidentUpdate): The incident update that was created
    update_fields (list[str]): The fields that were updated
    old_priority (Priority, optional): The old priority of the incident (optional kwarg)
"""

incident_key_events_updated = django.dispatch.Signal()
"""Signal sent when an incident's key events are updated.

Args:
    incident (Incident): The incident that was updated
"""

postmortem_created = django.dispatch.Signal()
"""Signal sent when a postmortem is created.

Args:
    sender (str | Any): The sender of the signal __name__
    incident (Incident): The incident for which the postmortem was created
"""

get_invites = django.dispatch.Signal()
"""Signal sent to retrieve the list of users to invite for an incident.

Args:
    incident (Incident): The incident for which to retrieve the list of users to invite.

Returns:
    users (list[User]): The list of users to invite.
"""

create_incident_conversation = django.dispatch.Signal()
"""Signal sent to create a conversation for an incident.

Args:
    incident (Incident): The incident for which to create a conversation.
"""
