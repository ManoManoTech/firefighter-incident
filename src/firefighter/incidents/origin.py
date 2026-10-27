"""Origin of an incident: internal, or a third-party partner.

The origin is independent of the status: a real incident (CLOSED) can come from a
partner, while a REJECTED incident was not a real one at all. A Commander records it
at mitigation (Key Events), may set it any time from the Edit modal, and confirms it
when closing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from firefighter.incidents.enums import IncidentOrigin
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.incidents.models.partner import Partner
from firefighter.incidents.signals import incident_origin_updated, partner_created

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)

ORIGIN_UPDATED_EVENT_TYPE = "origin_updated"
"""`IncidentUpdate.event_type` recording who set the origin, and when."""


def origin_label(incident: Incident) -> str:
    """Human-readable origin, e.g. "Partner: Algolia"."""
    if incident.origin != IncidentOrigin.PARTNER:
        return IncidentOrigin.INTERNAL.label
    if incident.partner is None:
        return "Partner (unspecified)"
    return f"Partner: {incident.partner.name}"


def resolve_partner(
    partner: Partner | None,
    new_partner_name: str | None,
    *,
    user: User | None,
    incident: Incident,
) -> Partner | None:
    """The selected partner, or the one named in "Not in the list? Add it".

    A selected partner wins over a typed name. A typed name matching an existing
    partner (case insensitively) reuses it; otherwise the partner is created, not
    reviewed, and `partner_created` is sent so that someone curates the list.
    """
    if partner is not None:
        return partner
    if not new_partner_name or not new_partner_name.strip():
        return None
    resolved, created = Partner.objects.get_or_create_by_name(
        new_partner_name, created_by=user
    )
    if created:
        logger.info(
            "Partner %r added by %s for incident #%s", resolved.name, user, incident.id
        )
        partner_created.send_robust(__name__, partner=resolved, incident=incident)
    return resolved


def apply_origin(
    incident: Incident,
    origin: IncidentOrigin | str,
    partner: Partner | None,
    *,
    user: User | None,
) -> bool:
    """Set the origin of the incident and record the change. Returns whether it changed."""
    origin = IncidentOrigin(origin)
    if origin != IncidentOrigin.PARTNER:
        partner = None
    if incident.origin == origin and incident.partner_id == (
        partner.id if partner else None
    ):
        return False

    incident.origin = origin
    incident.partner = partner
    incident.save(update_fields=["origin", "partner", "updated_at"])
    IncidentUpdate.objects.create(
        incident=incident,
        event_type=ORIGIN_UPDATED_EVENT_TYPE,
        message=f"Origin set to {origin_label(incident)}",
        created_by=user,
    )
    incident_origin_updated.send_robust(__name__, incident=incident, user=user)
    return True
