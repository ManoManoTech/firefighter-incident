from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Never

from django.dispatch.dispatcher import receiver

from firefighter.incidents import signals
from firefighter.pagerduty.models import PagerDutyUser

if TYPE_CHECKING:
    from firefighter.incidents.models import Incident
    from firefighter.incidents.models.user import User
logger = logging.getLogger(__name__)


@receiver(signal=signals.get_invites)
def get_invites_from_pagerduty(
    incident: Incident,
    **kwargs: Never,
) -> list[User]:
    if incident.private:
        return []
    return PagerDutyUser.objects.get_current_on_call_users_l1()
