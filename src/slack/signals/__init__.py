from __future__ import annotations

import django.dispatch

from slack.signals.incident_closed import incident_closed_slack

incident_channel_done = django.dispatch.Signal()
