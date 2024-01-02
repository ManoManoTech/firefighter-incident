from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_RAID: bool = config("ENABLE_RAID", cast=bool, default=False)
"Enable the Raid app. Jira app must be enabled and configured as well."

if ENABLE_RAID:
    INSTALLED_APPS += ("firefighter.raid",)

    RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = config("RAID_DEFAULT_JIRA_QRAFT_USER_ID")
    "The default Jira user ID to use for creating issues"

    RAID_JIRA_PROJECT_KEY: str = config("RAID_JIRA_PROJECT_KEY")
    "The Jira project key to use for creating issues, e.g. 'INC'"

    RAID_QUALIFIER_URL: str = config("RAID_QUALIFIER_URL")
    "Link to the board with issues to qualify"

    RAID_JIRA_USER_IDS: dict[str, str] = {}
    "Mapping of domain to default Jira user ID"
