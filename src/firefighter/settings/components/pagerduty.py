from __future__ import annotations

from firefighter.settings.components.common import INSTALLED_APPS
from firefighter.settings.settings_utils import config

ENABLE_PAGERDUTY: bool = config("ENABLE_PAGERDUTY", cast=bool)

if ENABLE_PAGERDUTY:
    INSTALLED_APPS.append("pagerduty")

    PAGERDUTY_API_KEY: str = config("PAGERDUTY_API_KEY")
    PAGERDUTY_ACCOUNT_EMAIL: str = config("PAGERDUTY_ACCOUNT_EMAIL")
    PAGERDUTY_URL: str = config("PAGERDUTY_URL", default="https://api.pagerduty.com")
