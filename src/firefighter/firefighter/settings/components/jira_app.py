from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_JIRA: bool = config("ENABLE_JIRA", cast=bool, default=False)

if ENABLE_JIRA:
    INSTALLED_APPS += ("firefighter.jira_app",)
    RAID_JIRA_API_USER: str = config("RAID_JIRA_API_USER")
    RAID_JIRA_API_PASSWORD: str = config("RAID_JIRA_API_PASSWORD")
    RAID_JIRA_API_URL: str = config("RAID_JIRA_API_URL")

    # If no protocol, add https
    if not RAID_JIRA_API_URL.startswith("http"):
        RAID_JIRA_API_URL = f"https://{RAID_JIRA_API_URL}"
