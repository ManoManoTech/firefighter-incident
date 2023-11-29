from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Never

from django.dispatch.dispatcher import receiver

from incidents import signals
from pagerduty.models import PagerDutyUser

if TYPE_CHECKING:
    from incidents.models import Incident
    from incidents.models.user import User
logger = logging.getLogger(__name__)


@receiver(signal=signals.get_invites)
def get_invites_from_pagerduty(
    incident: Incident,
    **kwargs: Never,
) -> list[User]:
    if incident.private:
        return []
    return PagerDutyUser.objects.get_current_on_call_users_l1()
