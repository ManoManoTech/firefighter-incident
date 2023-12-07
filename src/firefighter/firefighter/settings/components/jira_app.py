from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_JIRA: bool = config("ENABLE_JIRA", cast=bool, default=False)
"Enable the Jira app."

if ENABLE_JIRA:
    INSTALLED_APPS += ("firefighter.jira_app",)

    RAID_JIRA_API_USER: str = config("RAID_JIRA_API_USER")
    """The Jira API user to use."""
    RAID_JIRA_API_PASSWORD: str = config("RAID_JIRA_API_PASSWORD")
    """The Jira API password to use."""
    RAID_JIRA_API_URL: str = config("RAID_JIRA_API_URL")
    """The Jira API URL to use. If no protocol is defined, https will be used."""

    if not RAID_JIRA_API_URL.startswith("http"):
        RAID_JIRA_API_URL = f"https://{RAID_JIRA_API_URL}"
    RAID_JIRA_API_URL = RAID_JIRA_API_URL.rstrip("/")
