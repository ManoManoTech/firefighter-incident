from __future__ import annotations

from django.conf import settings

from firefighter.pagerduty.signals.get_invites_from_pagerduty import (
    get_invites_from_pagerduty,
)

if settings.ENABLE_SLACK:
    from firefighter.pagerduty.signals.incident_channel_done_oncall import (
        incident_channel_done_oncall,
    )
