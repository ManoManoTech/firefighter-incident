"""PagerDuty Celery tasks."""

from __future__ import annotations

from firefighter.pagerduty.tasks.fetch_oncall import fetch_oncalls
from firefighter.pagerduty.tasks.fetch_services import fetch_services
from firefighter.pagerduty.tasks.fetch_users import fetch_users
