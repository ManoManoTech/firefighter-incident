from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_PAGERDUTY: bool = config("ENABLE_PAGERDUTY", cast=bool, default=False)
"""Enable PagerDuty integration."""

if ENABLE_PAGERDUTY:
    INSTALLED_APPS.append("firefighter.pagerduty")

    PAGERDUTY_API_KEY: str = config("PAGERDUTY_API_KEY")
    """PagerDuty API key."""
    PAGERDUTY_ACCOUNT_EMAIL: str = config("PAGERDUTY_ACCOUNT_EMAIL")
    """PagerDuty account email, linked to the API key."""
    PAGERDUTY_URL: str = config("PAGERDUTY_URL", default="https://api.pagerduty.com")
    """PagerDuty API URL."""
